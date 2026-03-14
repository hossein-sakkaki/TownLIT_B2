# apps/accounts/services/townlit_verification_service.py

from django.db import transaction
from django.utils import timezone
from django.core.exceptions import PermissionDenied

from apps.accounts.models.townlit_verification import (
    TownlitVerificationGrant,
    TownlitVerificationAuditLog,
)
from apps.accounts.services.townlit_verification_audit import (
    log_townlit_verification_event,
)
from apps.accounts.constants.townlit_verification import (
    TV_ACTION_ADMIN_GRANT,
    TV_ACTION_ADMIN_REVOKE,
    TV_SOURCE_ADMIN,
)


def _safe_reason(value, max_length=1000):
    if not value:
        return ""
    if isinstance(value, str):
        return value[:max_length]
    return str(value)[:max_length]


@transaction.atomic
def admin_mark_townlit_verified(*, actor, target_member, reason=""):
    if not getattr(actor, "is_superuser", False):
        raise PermissionDenied("Only TownLIT superuser can manually grant TownLIT Gold.")

    safe_reason = _safe_reason(reason) or "Admin manually granted TownLIT Gold"
    previous_status = "verified" if target_member.is_townlit_verified else "not_verified"

    target_member.is_townlit_verified = True
    if not target_member.townlit_verified_at:
        target_member.townlit_verified_at = timezone.now()
    target_member.townlit_verified_reason = safe_reason
    target_member.save(update_fields=[
        "is_townlit_verified",
        "townlit_verified_at",
        "townlit_verified_reason",
    ])

    active_grant = (
        TownlitVerificationGrant.objects
        .select_for_update()
        .filter(member=target_member, is_active=True)
        .first()
    )

    if active_grant:
        active_grant.source = TownlitVerificationGrant.SOURCE_ADMIN
        active_grant.reason = safe_reason
        active_grant.approved_by = actor
        active_grant.save(update_fields=["source", "reason", "approved_by"])
    else:
        TownlitVerificationGrant.objects.create(
            member=target_member,
            source=TownlitVerificationGrant.SOURCE_ADMIN,
            reason=safe_reason,
            approved_by=actor,
            is_active=True,
        )

    log_townlit_verification_event(
        member=target_member,
        action=TV_ACTION_ADMIN_GRANT,
        source=TV_SOURCE_ADMIN,
        actor=actor,
        reason=safe_reason,
        previous_status=previous_status,
        new_status="verified",
        metadata={"scope": "townlit_verification"},
    )

    return target_member


@transaction.atomic
def admin_revoke_townlit_verified(*, actor, target_member, reason=""):
    if not getattr(actor, "is_superuser", False):
        raise PermissionDenied("Only TownLIT superuser can manually revoke TownLIT Gold.")

    safe_reason = _safe_reason(reason) or "Admin revoked TownLIT Gold"
    previous_status = "verified" if target_member.is_townlit_verified else "not_verified"

    target_member.is_townlit_verified = False
    target_member.townlit_verified_reason = safe_reason
    target_member.save(update_fields=[
        "is_townlit_verified",
        "townlit_verified_reason",
    ])

    active_grant = (
        TownlitVerificationGrant.objects
        .select_for_update()
        .filter(member=target_member, is_active=True)
        .first()
    )
    if active_grant:
        active_grant.revoke()

    log_townlit_verification_event(
        member=target_member,
        action=TV_ACTION_ADMIN_REVOKE,
        source=TV_SOURCE_ADMIN,
        actor=actor,
        reason=safe_reason,
        previous_status=previous_status,
        new_status="not_verified",
        metadata={"scope": "townlit_verification"},
    )

    return target_member