# apps/accounts/constants/identity_verification.py

"""
Identity verification configuration for TownLIT.
"""

# Verification methods
IV_METHOD_PROVIDER = "provider"
IV_METHOD_ADMIN = "admin"

IDENTITY_VERIFICATION_METHOD_CHOICES = [
    (IV_METHOD_PROVIDER, "Provider"),
    (IV_METHOD_ADMIN, "TownLIT Admin (Manual)"),
]


# Minimum trust score required
TRUST_SCORE_VERIFICATION_THRESHOLD = 60


# Verification status
IV_STATUS_PENDING = "pending"
IV_STATUS_VERIFIED = "verified"
IV_STATUS_REJECTED = "rejected"
IV_STATUS_REVOKED = "revoked"

IDENTITY_VERIFICATION_STATUS_CHOICES = [
    (IV_STATUS_PENDING, "Pending"),
    (IV_STATUS_VERIFIED, "Verified"),
    (IV_STATUS_REJECTED, "Rejected"),
    (IV_STATUS_REVOKED, "Revoked"),
]


# Verification level
IV_LEVEL_BASIC = "basic"
IV_LEVEL_STRONG = "strong"
IV_LEVEL_PROTECTED = "protected"

IDENTITY_VERIFICATION_LEVEL_CHOICES = [
    (IV_LEVEL_BASIC, "Basic"),
    (IV_LEVEL_STRONG, "Strong"),
    (IV_LEVEL_PROTECTED, "Protected"),
]


# Sensitive identity fields
IDENTITY_SENSITIVE_FIELDS = (
    "name",
    "family",
    "birthday",
    "gender",
    "country",
)