# apps/accounts/services/identity_verification_service.py
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import PermissionDenied

from apps.accounts.models import IdentityVerification
from apps.accounts.constants import (
    IV_STATUS_VERIFIED, IV_STATUS_REVOKED,
    IV_METHOD_ADMIN,
)

def get_or_create_iv(user, defaults=None):
    defaults = defaults or {}
    iv, _ = IdentityVerification.objects.get_or_create(
        user=user,
        defaults=defaults
    )
    return iv

@transaction.atomic
def admin_mark_identity_verified(*, actor, target_user, level="strong", reason=""):
    """
    Manual identity verification by TownLIT Superuser.
    - Creates IdentityVerification if missing.
    - Sets method=admin, status=verified, verified_at=now.
    """
    if not getattr(actor, "is_superuser", False):
        raise PermissionDenied("Only TownLIT superuser can manually verify identity.")

    iv = get_or_create_iv(
        target_user,
        defaults={
            "method": IV_METHOD_ADMIN,
            "status": IV_STATUS_VERIFIED,
            "level": level,
            "verified_at": timezone.now(),
        }
    )

    iv.method = IV_METHOD_ADMIN
    iv.status = IV_STATUS_VERIFIED
    iv.level = level
    iv.verified_at = timezone.now()
    iv.revoked_at = None
    iv.rejected_at = None
    if reason:
        iv.notes = (reason[:1000] if isinstance(reason, str) else str(reason)[:1000])
    iv.save(update_fields=[
        "method", "status", "level",
        "verified_at", "revoked_at", "rejected_at",
        "notes", "updated_at"
    ])

    return iv


@transaction.atomic
def admin_revoke_identity(*, actor, target_user, reason="Admin revoke"):
    """
    Manual revoke by TownLIT Superuser.
    """
    if not getattr(actor, "is_superuser", False):
        raise PermissionDenied("Only TownLIT superuser can revoke identity.")

    iv = get_or_create_iv(target_user)
    iv.status = IV_STATUS_REVOKED
    iv.revoked_at = timezone.now()
    if reason:
        iv.notes = (reason[:1000] if isinstance(reason, str) else str(reason)[:1000])
    iv.save(update_fields=["status", "revoked_at", "notes", "updated_at"])
    return iv
