# apps/accounts/services/townlit_engine.py

from django.utils import timezone
from django.db import transaction

from apps.accounts.constants import townlit_weights as W
from apps.accounts.services.townlit_profile import (
    get_member_missing_townlit_requirements,
)
from apps.accounts.services.townlit_score import (
    calculate_member_townlit_score,
)
from apps.profiles.models import Member


def get_member_townlit_state(member: Member) -> dict:
    """
    Full TownLIT gold state for UI + automation.
    """
    score = calculate_member_townlit_score(member)
    threshold = W.TOWNLIT_GOLD_THRESHOLD
    missing_requirements = get_member_missing_townlit_requirements(member)

    hard_requirements_ready = len(missing_requirements) == 0
    score_ready = score >= threshold

    already_gold = bool(member.is_townlit_verified)

    return {
        "score": score,
        "threshold": threshold,
        "remaining_score": max(threshold - score, 0),
        "hard_requirements_ready": hard_requirements_ready,
        "score_ready": score_ready,
        "missing_requirements": missing_requirements,
        "eligible_for_initial_gold_unlock": hard_requirements_ready and score_ready,
        "already_townlit_verified": already_gold,
        "identity_verified": bool(getattr(member.user, "is_verified_identity", False)),
    }


@transaction.atomic
def evaluate_and_apply_member_townlit_badge(member: Member) -> dict:
    """
    Auto-apply / auto-revoke TownLIT gold badge.

    Rules:
    1) If member is not currently gold:
       - grant gold only if hard requirements are complete AND score threshold is reached.

    2) If member is already gold:
       - keep gold even if score drops below threshold
       - revoke gold if any hard requirement becomes missing
    """
    member = Member.objects.select_for_update().select_related("user").get(pk=member.pk)

    state = get_member_townlit_state(member)

    hard_ready = state["hard_requirements_ready"]
    score_ready = state["score_ready"]
    already_gold = state["already_townlit_verified"]

    changed = False

    if not already_gold:
        if hard_ready and score_ready:
            member.is_townlit_verified = True
            member.townlit_verified_at = timezone.now()
            member.townlit_verified_reason = "Auto-awarded after completing TownLIT gold requirements"
            changed = True

    else:
        # Gold already exists → only hard requirements can revoke it
        if not hard_ready:
            member.is_townlit_verified = False
            member.townlit_verified_reason = "Auto-revoked because required TownLIT gold profile conditions are no longer complete"
            changed = True
            # keep verified_at as historical timestamp

    if changed:
        member.save(update_fields=[
            "is_townlit_verified",
            "townlit_verified_at",
            "townlit_verified_reason",
        ])

    state["changed"] = changed
    state["is_townlit_verified"] = bool(member.is_townlit_verified)
    state["townlit_verified_at"] = member.townlit_verified_at
    state["townlit_verified_reason"] = member.townlit_verified_reason

    return state