# apps/profiles/services/townlit_verification/rules.py

from dataclasses import dataclass
from typing import Callable, TYPE_CHECKING
if TYPE_CHECKING:
    from apps.profiles.models import Member 

    
@dataclass(frozen=True)
class RuleResult:
    ok: bool
    code: str
    message: str

RuleFn = Callable[["Member"], RuleResult]

def ok(code: str = "ok", message: str = "OK") -> RuleResult:
    return RuleResult(True, code, message)

def fail(code: str, message: str) -> RuleResult:
    return RuleResult(False, code, message)


# ----------------------------
# Core rules
# ----------------------------

def rule_user_identity_prerequisite(member) -> RuleResult:
    # TownLIT verification requires verified human identity (CustomUser)
    if not getattr(member.user, "is_verified_identity", False):
        return fail(
            "identity_prerequisite_missing",
            "Verified human identity is required for TownLIT verification"
        )
    return ok()


def rule_biography(member) -> RuleResult:
    # Biography required (min length)
    bio = (member.biography or "").strip()
    if len(bio) < 50:
        return fail("biography_missing", "Biography is required (min 50 chars)")
    return ok()

def rule_vision(member) -> RuleResult:
    # Vision required (min length)
    vis = (member.vision or "").strip()
    if len(vis) < 50:
        return fail("vision_missing", "Vision is required (min 50 chars)")
    return ok()

def rule_spiritual_rebirth_day(member) -> RuleResult:
    # Rebirth day required
    if not member.spiritual_rebirth_day:
        return fail("rebirth_missing", "Spiritual rebirth day is required")
    return ok()

def rule_denomination_branch(member) -> RuleResult:
    # Denomination branch required
    if not (member.denomination_branch or "").strip():
        return fail("denomination_branch_missing", "Denomination branch is required")
    return ok()

def rule_service_types(member) -> RuleResult:
    # Must have at least one service type
    if not member.service_types.exists():
        return fail("service_types_missing", "At least one service type is required")
    return ok()


# ----------------------------
# Dependent rules (related models)
# ----------------------------

def rule_has_testimony(member) -> RuleResult:
    # Must have at least one testimony (any type)
    if not member.testimonies.exists():
        return fail("testimony_missing", "At least one testimony is required")
    return ok()

def rule_spiritual_gifts(member) -> RuleResult:
    # Must have spiritual gifts record + at least one gift
    gifts_rel = getattr(member, "memberspiritualgifts", None)  # adjust related_name if you set one
    if not gifts_rel:
        return fail("spiritual_gifts_missing", "Spiritual gifts survey is required")
    if not gifts_rel.gifts.exists():
        return fail("spiritual_gifts_empty", "At least one spiritual gift is required")
    # Optional: require non-empty survey_results
    if not gifts_rel.survey_results:
        return fail("spiritual_gifts_results_missing", "Survey results are required")
    return ok()
