# apps/sanctuary/services/participants.py

from __future__ import annotations

from django.utils import timezone
from django.db import transaction, IntegrityError

from rest_framework.exceptions import PermissionDenied, ValidationError
from apps.sanctuary.models import SanctuaryParticipantProfile, SanctuaryParticipantAudit


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def _is_identity_verified(user) -> bool:
    return bool(getattr(user, "is_verified_identity", False))


def _is_townlit_verified(user) -> bool:
    """
    TownLIT verified is on Member model: user.member_profile.is_townlit_verified
    """
    mp = getattr(user, "member_profile", None)
    return bool(getattr(mp, "is_townlit_verified", False))


def get_or_create_profile(user) -> SanctuaryParticipantProfile:
    """
    Robust get_or_create for OneToOne profile (handles rare concurrent create).
    """
    try:
        profile, _ = SanctuaryParticipantProfile.objects.get_or_create(user=user)
        return profile
    except IntegrityError:
        # If two concurrent writers tried to create, the second may hit unique constraint.
        return SanctuaryParticipantProfile.objects.get(user=user)


def _locked_profile(user) -> SanctuaryParticipantProfile:
    """
    Lock the profile row if exists; if not exists create it safely within transaction.
    """
    # select_for_update() only locks existing rows; create path can still race,
    # so we catch IntegrityError as a safety net.
    try:
        profile, _ = (
            SanctuaryParticipantProfile.objects
            .select_for_update()
            .get_or_create(user=user)
        )
        return profile
    except IntegrityError:
        return (
            SanctuaryParticipantProfile.objects
            .select_for_update()
            .get(user=user)
        )


# ---------------------------------------------------------------------
# User Opt-in
# ---------------------------------------------------------------------
@transaction.atomic
def user_opt_in(user) -> SanctuaryParticipantProfile:
    # Gate checks (order doesn't matter, but messages are clearer this way)
    if not _is_identity_verified(user):
        raise PermissionDenied("Identity verification required.")

    # ✅ FIX: TownLIT verification is on Member
    if not _is_townlit_verified(user):
        raise PermissionDenied("TownLIT verification required.")

    profile = _locked_profile(user)

    if not profile.is_eligible:
        raise PermissionDenied("You are not eligible for Sanctuary participation.")

    # Idempotent opt-in
    if profile.is_participant:
        return profile

    now = timezone.now()
    profile.is_participant = True
    profile.participant_opted_in_at = now
    profile.participant_opted_out_at = None
    profile.save(update_fields=[
        "is_participant",
        "participant_opted_in_at",
        "participant_opted_out_at",
        "updated_at",
    ])

    SanctuaryParticipantAudit.objects.create(
        profile=profile,
        action=SanctuaryParticipantAudit.ACTION_OPT_IN,
        actor=None,
        reason=None,
        metadata={},
    )
    return profile


# ---------------------------------------------------------------------
# User Opt-out
# ---------------------------------------------------------------------
@transaction.atomic
def user_opt_out(user) -> SanctuaryParticipantProfile:
    # Idempotent: if profile doesn't exist yet, create it and treat as opted-out
    profile = _locked_profile(user)

    if not profile.is_participant:
        return profile

    now = timezone.now()
    profile.is_participant = False
    profile.participant_opted_out_at = now
    profile.save(update_fields=[
        "is_participant",
        "participant_opted_out_at",
        "updated_at",
    ])

    SanctuaryParticipantAudit.objects.create(
        profile=profile,
        action=SanctuaryParticipantAudit.ACTION_OPT_OUT,
        actor=None,
        reason=None,
        metadata={},
    )
    return profile


# ---------------------------------------------------------------------
# Admin Set Eligibility
# ---------------------------------------------------------------------
@transaction.atomic
def admin_set_eligibility(
    *,
    user,
    is_eligible: bool,
    admin_user,
    reason: str | None = None,
    metadata: dict | None = None,
) -> SanctuaryParticipantProfile:
    if not getattr(admin_user, "is_staff", False):
        raise PermissionDenied("Admin required.")

    profile = _locked_profile(user)

    is_eligible = bool(is_eligible)
    reason_clean = (reason or "").strip()

    # Require reason when blocking
    if (is_eligible is False) and not reason_clean:
        raise ValidationError("Reason is required when setting eligible to False.")

    # Idempotent
    if profile.is_eligible == is_eligible:
        return profile

    now = timezone.now()

    # Apply changes
    profile.is_eligible = is_eligible
    profile.eligible_changed_at = now
    profile.eligible_changed_by = admin_user
    profile.eligible_reason = None if is_eligible else reason_clean

    # Auto opt-out if blocked (recommended)
    if not is_eligible:
        profile.is_participant = False
        profile.participant_opted_out_at = now

    # 🔒 Prevent signal double-run (service is the canonical path)
    profile._skip_council_actions = True

    profile.save(update_fields=[
        "is_eligible",
        "eligible_changed_at",
        "eligible_changed_by",
        "eligible_reason",
        "is_participant",
        "participant_opted_out_at",
        "updated_at",
    ])

    SanctuaryParticipantAudit.objects.create(
        profile=profile,
        action=(
            SanctuaryParticipantAudit.ACTION_ELIGIBLE_TRUE
            if is_eligible
            else SanctuaryParticipantAudit.ACTION_ELIGIBLE_FALSE
        ),
        actor=admin_user,
        reason=reason_clean if not is_eligible else None,
        metadata=metadata or {},
    )

    # ✅ Post-commit side-effects (real-time council safety)
    if not is_eligible:
        def _after_commit():
            try:
                from apps.sanctuary.services.council_actions import replace_user_in_open_councils
                replace_user_in_open_councils(
                    user_id=user.id,
                    reason=reason_clean,
                    actor_id=getattr(admin_user, "id", None),
                )
            except Exception:
                # Fallback: at least kick user out so they can't vote
                try:
                    from apps.sanctuary.services.council_actions import kick_user_from_open_councils
                    kick_user_from_open_councils(user_id=user.id)
                except Exception:
                    pass

        transaction.on_commit(_after_commit)

    return profile
