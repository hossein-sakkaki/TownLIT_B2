# apps/accounts/services/identity_finalize.py

from django.db import transaction
from django.utils import timezone

from apps.accounts.models.identity import IdentityVerification, IdentityGrant
from apps.accounts.services.identity_audit import log_identity_event
from apps.accounts.constants.identity_audit import (
    IA_VERIFY,
    IA_REJECT,
    IA_SOURCE_VERIFF,
)
from apps.accounts.constants.identity_verification import (
    IV_STATUS_VERIFIED,
    IV_STATUS_REJECTED,
    IV_STATUS_REVOKED,
    IV_METHOD_PROVIDER,
)


def _safe_reason(value, max_length=1000):
    # Normalize reason text
    if not value:
        return ""
    if isinstance(value, str):
        return value[:max_length]
    return str(value)[:max_length]


@transaction.atomic
def grant_verified_identity(
    *,
    user,
    level="strong",
    source=IdentityGrant.SOURCE_SYSTEM,
    reason="Identity verified via provider",
):
    # Ensure exactly one active identity grant
    active_grant = (
        IdentityGrant.objects
        .select_for_update()
        .filter(user=user, is_active=True)
        .first()
    )

    if active_grant:
        changed = False

        if active_grant.level != level:
            active_grant.level = level
            changed = True

        if active_grant.source != source:
            active_grant.source = source
            changed = True

        if active_grant.reason != reason:
            active_grant.reason = reason
            changed = True

        if changed:
            active_grant.save(update_fields=["level", "source", "reason"])

        return active_grant

    return IdentityGrant.objects.create(
        user=user,
        source=source,
        level=level,
        reason=reason,
        is_active=True,
    )


@transaction.atomic
def revoke_active_identity_grant(*, user):
    # Revoke current active identity grant
    active_grant = (
        IdentityGrant.objects
        .select_for_update()
        .filter(user=user, is_active=True)
        .first()
    )

    if active_grant:
        active_grant.revoke()

    return active_grant


@transaction.atomic
def finalize_provider_identity_approved(
    *,
    iv,
    provider_payload=None,
    risk_labels=None,
):
    """
    Finalize approved provider verification.
    Idempotent and safe.
    """
    iv = IdentityVerification.objects.select_for_update().get(pk=iv.pk)
    previous_status = iv.status

    if iv.status == IV_STATUS_VERIFIED:
        # Backfill grant if old data missed it
        grant_verified_identity(
            user=iv.user,
            level=iv.level or "strong",
            source=IdentityGrant.SOURCE_SYSTEM,
            reason="Identity verified via Veriff",
        )
        return iv

    iv.method = IV_METHOD_PROVIDER
    iv.status = IV_STATUS_VERIFIED
    iv.level = "strong"
    iv.verified_at = timezone.now()
    iv.revoked_at = None
    iv.rejected_at = None
    iv.risk_flag = bool(risk_labels)

    if provider_payload is not None:
        iv.provider_payload = provider_payload

    iv.save(update_fields=[
        "method",
        "status",
        "level",
        "verified_at",
        "revoked_at",
        "rejected_at",
        "risk_flag",
        "provider_payload",
        "updated_at",
    ])

    grant_verified_identity(
        user=iv.user,
        level=iv.level,
        source=IdentityGrant.SOURCE_SYSTEM,
        reason="Identity verified via Veriff",
    )

    log_identity_event(
        user=iv.user,
        identity_verification=iv,
        action=IA_VERIFY,
        source=IA_SOURCE_VERIFF,
        previous_status=previous_status,
        new_status=iv.status,
        metadata={"risk": risk_labels or []},
    )

    return iv


@transaction.atomic
def finalize_provider_identity_rejected(
    *,
    iv,
    reason=None,
    provider_payload=None,
    risk_labels=None,
):
    """
    Finalize rejected provider verification.
    """
    iv = IdentityVerification.objects.select_for_update().get(pk=iv.pk)
    previous_status = iv.status

    if iv.status in {IV_STATUS_REJECTED, IV_STATUS_REVOKED}:
        # Keep grant state consistent
        revoke_active_identity_grant(user=iv.user)
        return iv

    iv.method = IV_METHOD_PROVIDER
    iv.status = IV_STATUS_REJECTED
    iv.rejected_at = timezone.now()
    iv.risk_flag = bool(risk_labels)

    if reason:
        iv.notes = _safe_reason(reason)

    if provider_payload is not None:
        iv.provider_payload = provider_payload

    iv.save(update_fields=[
        "method",
        "status",
        "rejected_at",
        "risk_flag",
        "notes",
        "provider_payload",
        "updated_at",
    ])

    revoke_active_identity_grant(user=iv.user)

    log_identity_event(
        user=iv.user,
        identity_verification=iv,
        action=IA_REJECT,
        source=IA_SOURCE_VERIFF,
        previous_status=previous_status,
        new_status=iv.status,
        reason=_safe_reason(reason),
        metadata={"risk": risk_labels or []},
    )

    return iv