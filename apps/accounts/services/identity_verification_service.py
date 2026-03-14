# apps/accounts/services/identity_verification_service.py

from django.utils import timezone
from django.db import transaction
from django.core.exceptions import PermissionDenied

from apps.accounts.models import IdentityVerification, IdentityGrant, IdentityAuditLog
from apps.accounts.constants.identity_verification import (
    IV_STATUS_VERIFIED,
    IV_STATUS_REVOKED,
    IV_METHOD_ADMIN,
)
from apps.accounts.constants.identity_audit import (
    IA_VERIFY,
    IA_REVOKE,
    IA_SOURCE_ADMIN,
)
from apps.accounts.services.identity_audit import log_identity_event


def get_or_create_iv(user, defaults=None):
    # Get or create identity verification row
    defaults = defaults or {}
    iv, _ = IdentityVerification.objects.get_or_create(
        user=user,
        defaults=defaults,
    )
    return iv


def _safe_reason(value, max_length=1000):
    # Normalize reason text
    if not value:
        return ""
    if isinstance(value, str):
        return value[:max_length]
    return str(value)[:max_length]


@transaction.atomic
def admin_mark_identity_verified(*, actor, target_user, level="strong", reason=""):
    """
    Manual identity verification by TownLIT superuser.
    - Creates IdentityVerification if missing
    - Marks IV as verified
    - Creates or updates active IdentityGrant
    """
    if not getattr(actor, "is_superuser", False):
        raise PermissionDenied("Only TownLIT superuser can manually verify identity.")

    safe_reason = _safe_reason(reason) or "Identity manually verified by TownLIT admin"

    iv = get_or_create_iv(
        target_user,
        defaults={
            "method": IV_METHOD_ADMIN,
            "status": IV_STATUS_VERIFIED,
            "level": level,
            "verified_at": timezone.now(),
            "notes": safe_reason,
        },
    )

    previous_status = iv.status

    iv.method = IV_METHOD_ADMIN
    iv.status = IV_STATUS_VERIFIED
    iv.level = level
    iv.verified_at = timezone.now()
    iv.revoked_at = None
    iv.rejected_at = None
    iv.notes = safe_reason

    iv.save(update_fields=[
        "method",
        "status",
        "level",
        "verified_at",
        "revoked_at",
        "rejected_at",
        "notes",
        "updated_at",
    ])

    active_grant = (
        IdentityGrant.objects
        .select_for_update()
        .filter(user=target_user, is_active=True)
        .first()
    )

    if active_grant:
        active_grant.source = IdentityGrant.SOURCE_ADMIN
        active_grant.level = level
        active_grant.reason = safe_reason
        active_grant.approved_by = actor
        active_grant.save(update_fields=[
            "source",
            "level",
            "reason",
            "approved_by",
        ])
    else:
        IdentityGrant.objects.create(
            user=target_user,
            source=IdentityGrant.SOURCE_ADMIN,
            level=level,
            reason=safe_reason,
            approved_by=actor,
            is_active=True,
        )

    log_identity_event(
        user=target_user,
        identity_verification=iv,
        action=IA_VERIFY,
        source=IA_SOURCE_ADMIN,
        actor=actor,
        previous_status=previous_status,
        new_status=iv.status,
        reason=safe_reason,
    )

    return iv


@transaction.atomic
def admin_revoke_identity(*, actor, target_user, reason="Admin revoke"):
    """
    Manual revoke by TownLIT superuser.
    - Marks IV as revoked
    - Revokes active IdentityGrant
    """
    if not getattr(actor, "is_superuser", False):
        raise PermissionDenied("Only TownLIT superuser can revoke identity.")

    safe_reason = _safe_reason(reason) or "Admin revoke"

    iv = get_or_create_iv(target_user)
    previous_status = iv.status

    iv.method = IV_METHOD_ADMIN
    iv.status = IV_STATUS_REVOKED
    iv.revoked_at = timezone.now()
    iv.notes = safe_reason

    iv.save(update_fields=[
        "method",
        "status",
        "revoked_at",
        "notes",
        "updated_at",
    ])

    active_grant = (
        IdentityGrant.objects
        .select_for_update()
        .filter(user=target_user, is_active=True)
        .first()
    )
    if active_grant:
        active_grant.revoke()

    log_identity_event(
        user=target_user,
        identity_verification=iv,
        action=IA_REVOKE,
        source=IA_SOURCE_ADMIN,
        actor=actor,
        previous_status=previous_status,
        new_status=iv.status,
        reason=safe_reason,
    )

    return iv



@transaction.atomic
def admin_unverify_identity(actor, target_user, reason="Admin unverified identity"):
    """
    Fully remove verified identity state from a user.

    This revokes:
    - IdentityVerification status (if currently verified)
    - Any active IdentityGrant rows

    The goal is that target_user.is_verified_identity becomes False.
    """
    now = timezone.now()

    iv = getattr(target_user, "identity_verification", None)

    # 1) Revoke verification record if needed
    if iv and iv.status == "verified":
        previous_status = iv.status
        iv.status = "revoked"
        iv.revoked_at = now
        iv.save(update_fields=["status", "revoked_at", "updated_at"])

        IdentityAuditLog.objects.create(
            user=target_user,
            identity_verification=iv,
            action="revoked",
            source="admin",
            actor=actor,
            reason=reason,
            previous_status=previous_status,
            new_status=iv.status,
            metadata={"scope": "identity_verification"},
        )

    # 2) Revoke all active grants
    active_grants = IdentityGrant.objects.filter(user=target_user, is_active=True)

    for grant in active_grants:
        grant.is_active = False
        grant.revoked_at = now
        grant.save(update_fields=["is_active", "revoked_at"])

        IdentityAuditLog.objects.create(
            user=target_user,
            identity_verification=iv if iv else None,
            action="revoked",
            source="admin",
            actor=actor,
            reason=reason,
            previous_status="grant_active",
            new_status="grant_revoked",
            metadata={
                "scope": "identity_grant",
                "grant_id": grant.id,
                "grant_level": grant.level,
                "grant_source": grant.source,
            },
        )

    return True