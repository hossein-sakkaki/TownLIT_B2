# apps/sanctuary/services/protection.py

from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied

from apps.sanctuary.models import SanctuaryProtectionLabel


# Labels that lock edits (no one can edit while active)
EDIT_LOCK_LABELS = {
    SanctuaryProtectionLabel.TRADITION_SPECIFIC_PERSPECTIVE,
}


# Active protection labels -------------------------------------------------
def active_labels_for(obj):
    """Return active protection labels for a target object."""
    if not obj:
        return SanctuaryProtectionLabel.objects.none()

    ct = ContentType.objects.get_for_model(obj.__class__)
    now = timezone.now()

    return SanctuaryProtectionLabel.objects.filter(
        content_type=ct,
        object_id=obj.pk,
        is_active=True,
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now)
    )


# Locks --------------------------------------------------------------------
def is_edit_locked(obj) -> bool:
    """True if object has an active label that locks edits."""
    return active_labels_for(obj).filter(label_type__in=EDIT_LOCK_LABELS).exists()


# Permissions --------------------------------------------------------------
def assert_can_update(obj):
    """
    Block ALL updates if locked (even staff/admin).
    Note: this does NOT block delete.
    """
    if obj and is_edit_locked(obj):
        raise PermissionDenied(
            "This content is temporarily locked due to Sanctuary protection."
        )
