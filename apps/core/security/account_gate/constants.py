# apps/core/security/account_gate/constants.py

"""
Central API gate constants for temporarily restricted owner accounts.

This gate is separate from LITShield.
It protects app-wide access when the authenticated owner's profile
is temporarily unavailable for safety/privacy reasons.
"""

RESTRICTED_OWNER_CODE = "profile_temporarily_unavailable"

RESTRICTED_OWNER_DETAIL = (
    "Your profile is currently unavailable. "
    "Please contact TownLIT Support for more information."
)

RESTRICTED_OWNER_PROFILE_GATE = {
    "key": "profile_temporarily_unavailable",
    "reason": "temporarily_unavailable",
    "owner_message": RESTRICTED_OWNER_DETAIL,
}

API_PREFIX = "/api/v1/"

# Exact API paths still allowed while the owner account is restricted.
# Keep this list intentionally small.
RESTRICTED_OWNER_ALLOWED_EXACT_PATHS = {
    "/api/v1/profiles/members/my-profile/",
    "/api/v1/profiles/me/",

    "/api/v1/accounts/me/",
    "/api/v1/accounts/auth/me/",
    "/api/v1/accounts/logout/",
    "/api/v1/accounts/auth/logout/",
    "/api/v1/accounts/token/refresh/",
    "/api/v1/accounts/auth/token/refresh/",
    "/api/v1/accounts/token/verify/",
    "/api/v1/accounts/auth/token/verify/",

    # LITShield session cleanup must be allowed during logout.
    "/api/v1/security/logout/",
}

# Prefixes allowed while restricted.
# Use only for endpoints that are safe and necessary.
RESTRICTED_OWNER_ALLOWED_PREFIXES = (
    # Main/public metadata such as terms/policies can stay available.
    "/api/v1/main/",
    "/api/v1/terms/",
    "/api/v1/policies/",

    # Security/account-gate future status endpoints.
    "/api/v1/security/account-gate/",
)