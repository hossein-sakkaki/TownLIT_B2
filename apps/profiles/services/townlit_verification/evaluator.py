# apps/profiles/services/townlit_verification/evaluator.py

from typing import List
from .rules import (
    RuleResult,
    rule_user_identity_prerequisite, rule_biography, rule_vision, rule_spiritual_rebirth_day,
    rule_denomination_branch, rule_service_types, rule_has_testimony, rule_spiritual_gifts
)

def get_default_rules():
    # Ordered rules (first fail wins)
    return [
        rule_user_identity_prerequisite,
        rule_biography,
        rule_vision,
        rule_spiritual_rebirth_day,
        rule_denomination_branch,
        rule_service_types,
        rule_has_testimony,
        rule_spiritual_gifts,
    ]

def evaluate_townlit_verification(member) -> RuleResult:
    # Evaluate all rules
    for rule in get_default_rules():
        res = rule(member)
        if not res.ok:
            return res
    return RuleResult(True, "eligible", "Eligible for TownLIT verification")
