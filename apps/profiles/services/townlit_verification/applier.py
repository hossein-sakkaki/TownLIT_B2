# apps/profiles/services/townlit_verification/applier.py

from django.utils import timezone
from .evaluator import evaluate_townlit_verification

def apply_townlit_verification(member, *, actor=None, source="system"):
    # Apply verification state based on rules (auto-approve / auto-revoke)
    res = evaluate_townlit_verification(member)

    should_be_verified = bool(res.ok)
    is_verified = bool(member.is_townlit_verified)

    if should_be_verified and not is_verified:
        member.is_townlit_verified = True
        member.townlit_verified_at = timezone.now()
        member.townlit_verified_reason = "auto_approved"
        member.save(update_fields=["is_townlit_verified", "townlit_verified_at", "townlit_verified_reason"])
        return {"changed": True, "status": "verified", "reason": res.code}

    if (not should_be_verified) and is_verified:
        member.is_townlit_verified = False
        member.townlit_verified_at = None
        member.townlit_verified_reason = res.code
        member.save(update_fields=["is_townlit_verified", "townlit_verified_at", "townlit_verified_reason"])
        return {"changed": True, "status": "revoked", "reason": res.code}

    # No change
    return {"changed": False, "status": "unchanged", "reason": res.code}
