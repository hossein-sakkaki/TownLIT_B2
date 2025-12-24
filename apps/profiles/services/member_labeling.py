# apps/profiles/services/member_labeling.py

def should_grant_townlit_member_label(member) -> bool:
    return bool(member and member.is_townlit_verified)
