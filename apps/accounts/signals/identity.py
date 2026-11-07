# apps/accounts/signals/identity.py
# TownLIT-Backend
#
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Invalidate verified identity when persisted identity attributes change.

A logical protected property (such as CustomUser.birthday) is not an ORM
column and must never be passed directly to QuerySet.only().
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from apps.accounts.constants.identity_verification import (
    IDENTITY_SENSITIVE_FIELDS,
    IV_STATUS_VERIFIED,
)
from apps.accounts.models.user import CustomUser


def _database_field_name(logical_name: str) -> str:
    """Resolve logical identity fields to their current persistence columns."""
    protected_specs = getattr(CustomUser, "protected_field_specs", {})
    if logical_name in protected_specs:
        return protected_specs[logical_name][0]
    return logical_name


def _persisted_identity_fields(update_fields):
    """Check only identity attributes included in a partial model save."""
    if update_fields is None:
        return tuple(IDENTITY_SENSITIVE_FIELDS)

    persisted = set(update_fields)
    return tuple(
        name
        for name in IDENTITY_SENSITIVE_FIELDS
        if name in persisted or _database_field_name(name) in persisted
    )


@receiver(pre_save, sender=CustomUser)
def stash_old_identity_fields(sender, instance: CustomUser, **kwargs):
    """Capture the previous logical values before the user row changes."""
    relevant_fields = _persisted_identity_fields(kwargs.get("update_fields"))
    instance._old_identity_snapshot = None
    instance._identity_fields_to_check = relevant_fields

    if not instance.pk or not relevant_fields:
        return

    db_fields = tuple(_database_field_name(name) for name in relevant_fields)

    try:
        old = CustomUser.objects.only(*db_fields).get(pk=instance.pk)
    except CustomUser.DoesNotExist:
        return

    # For protected fields, read through the logical property to decrypt.
    instance._old_identity_snapshot = {
        name: getattr(old, name)
        for name in relevant_fields
    }


@receiver(post_save, sender=CustomUser)
def revoke_identity_if_sensitive_fields_changed(
    sender,
    instance: CustomUser,
    created: bool,
    **kwargs,
):
    """Revoke verified identity only after a sensitive change is persisted."""
    old = instance.__dict__.pop("_old_identity_snapshot", None)
    relevant_fields = instance.__dict__.pop("_identity_fields_to_check", ())

    if created or old is None:
        return

    changed = [
        name
        for name in relevant_fields
        if old.get(name) != getattr(instance, name)
    ]
    if not changed:
        return

    iv = getattr(instance, "identity_verification", None)
    if not iv or iv.status != IV_STATUS_VERIFIED:
        return

    iv.status = "revoked"
    iv.revoked_at = timezone.now()
    iv.notes = f"Auto-revoked due to identity field change: {', '.join(changed)}"
    iv.save(update_fields=["status", "revoked_at", "notes", "updated_at"])
