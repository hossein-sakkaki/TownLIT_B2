# apps/sanctuary/services/participation_status.py

from typing import Dict, List
from django.utils import timezone

from apps.main.models import TermsAndPolicy, UserAgreement
from apps.sanctuary.models import SanctuaryParticipantProfile
from apps.main.constants import SANCTUARY_COUNCIL_RULES


def get_participation_status(user) -> Dict:
    """
    Single source of truth for Sanctuary participation state.
    Enforces policy availability, acceptance, and version validity.
    """

    # --------------------------------------------------
    # Identity verification gates
    # --------------------------------------------------
    is_verified_identity = bool(getattr(user, "is_verified_identity", False))
    is_townlit_verified = bool(getattr(user, "is_townlit_verified", False))

    # --------------------------------------------------
    # Sanctuary profile (system-level eligibility)
    # --------------------------------------------------
    try:
        profile = SanctuaryParticipantProfile.objects.get(user=user)
        is_system_eligible = bool(profile.is_eligible)
        eligible_reason = profile.eligible_reason
        is_participant = bool(profile.is_participant)
        opted_in_at = profile.participant_opted_in_at
        opted_out_at = profile.participant_opted_out_at
    except SanctuaryParticipantProfile.DoesNotExist:
        is_system_eligible = False
        eligible_reason = "profile_missing"
        is_participant = False
        opted_in_at = None
        opted_out_at = None

    # --------------------------------------------------
    # Active Sanctuary policy (latest)
    # --------------------------------------------------
    policy = (
        TermsAndPolicy.objects.filter(
            policy_type=SANCTUARY_COUNCIL_RULES,
            is_active=True,
        )
        .order_by("-last_updated")
        .first()
    )

    policy_available = bool(policy)
    requires_acceptance = bool(policy.requires_acceptance) if policy else False

    # --------------------------------------------------
    # User agreement check (version-aware)
    # --------------------------------------------------
    has_agreed = False
    agreed_at = None
    policy_version_mismatch = False

    if policy:
        agreement = (
            UserAgreement.objects.filter(
                user=user,
                policy=policy,
                is_latest_agreement=True,
            )
            .order_by("-agreed_at")
            .first()
        )

        if agreement:
            # Agreement exists
            has_agreed = True
            agreed_at = agreement.agreed_at

            # 🔒 POLICY VERSION ENFORCEMENT
            if agreement.policy_version_number != policy.version_number:
                policy_version_mismatch = True
                has_agreed = False  # invalidate agreement

    # --------------------------------------------------
    # Ineligible reasons (UI-level gates)
    # --------------------------------------------------
    ineligible_reasons: List[str] = []

    if not is_verified_identity:
        ineligible_reasons.append("identity_not_verified")

    if not is_townlit_verified:
        ineligible_reasons.append("townlit_not_verified")

    if not is_system_eligible:
        ineligible_reasons.append("not_eligible")

    if not policy_available:
        ineligible_reasons.append("policy_missing")

    if requires_acceptance and not has_agreed:
        if policy_version_mismatch:
            ineligible_reasons.append("policy_version_changed")
        else:
            ineligible_reasons.append("policy_not_accepted")

    # --------------------------------------------------
    # Eligible "right now" (policy-aware)
    # --------------------------------------------------
    eligible_now = (
        is_verified_identity
        and is_townlit_verified
        and is_system_eligible
        and policy_available
        and (not requires_acceptance or has_agreed)
    )

    # --------------------------------------------------
    # Final payload (Frontend contract)
    # --------------------------------------------------
    return {
        # Identity
        "is_verified_identity": is_verified_identity,
        "is_townlit_verified": is_townlit_verified,

        # Sanctuary core
        "is_sanctuary_participant": is_participant,
        "is_sanctuary_eligible": is_system_eligible,
        "eligible_reason": eligible_reason,
        "eligible_changed_at": profile.eligible_changed_at if is_system_eligible else None,

        "participant_opted_in_at": opted_in_at,
        "participant_opted_out_at": opted_out_at,

        # Policy metadata
        "policy_available": policy_available,
        "policy_type": policy.policy_type if policy else "",
        "policy_title": policy.title if policy else "",
        "policy_language": policy.language if policy else "",
        "policy_version_number": policy.version_number if policy else "",
        "policy_last_updated": policy.last_updated if policy else None,
        "requires_acceptance": requires_acceptance,

        # Agreement
        "has_agreed": has_agreed,
        "agreed_at": agreed_at,

        # UI helpers
        "eligible": eligible_now,
        "ineligible_reasons": ineligible_reasons,
    }
