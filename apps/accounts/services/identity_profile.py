# apps/accounts/services/identity_profile.py

def get_missing_identity_profile_fields(user):
    """
    Check required profile fields for provider verification.
    """
    missing = []

    if not user.name:
        missing.append("name")

    if not user.family:
        missing.append("family")

    if not user.birthday:
        missing.append("birthday")

    if not user.gender:
        missing.append("gender")

    if not getattr(user, "country", None):
        missing.append("country")

    if not getattr(user, "primary_language", None):
        missing.append("primary_language")

    return missing