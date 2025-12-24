# apps/accounts/signals/identity.py

from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils import timezone

from apps.accounts.constants import IDENTITY_SENSITIVE_FIELDS, IV_STATUS_VERIFIED
from apps.accounts.models import CustomUser, IdentityVerification

@receiver(pre_save, sender=CustomUser)
def stash_old_identity_fields(sender, instance: CustomUser, **kwargs):
    # Cache old values before save
    if not instance.pk:
        instance._old_identity_snapshot = None
        return
    try:
        old = CustomUser.objects.only(*IDENTITY_SENSITIVE_FIELDS).get(pk=instance.pk)
        instance._old_identity_snapshot = {f: getattr(old, f) for f in IDENTITY_SENSITIVE_FIELDS}
    except CustomUser.DoesNotExist:
        instance._old_identity_snapshot = None

@receiver(post_save, sender=CustomUser)
def revoke_identity_if_sensitive_fields_changed(sender, instance: CustomUser, created: bool, **kwargs):
    # Revoke verification if sensitive fields changed after being verified
    if created:
        return

    old = getattr(instance, "_old_identity_snapshot", None)
    if not old:
        return

    changed = []
    for f in IDENTITY_SENSITIVE_FIELDS:
        if old.get(f) != getattr(instance, f):
            changed.append(f)

    if not changed:
        return

    iv = getattr(instance, "identity_verification", None)
    if not iv or iv.status != IV_STATUS_VERIFIED:
        return

    # Revoke on identity changes
    iv.status = "revoked"
    iv.revoked_at = timezone.now()
    iv.notes = f"Auto-revoked due to identity field change: {', '.join(changed)}"
    iv.save(update_fields=["status", "revoked_at", "notes", "updated_at"])
