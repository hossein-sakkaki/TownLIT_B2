# apps/accounts/constants/townlit_verification.py

TV_ACTION_AUTO_AWARD = "auto_award"
TV_ACTION_ADMIN_GRANT = "admin_grant"
TV_ACTION_AUTO_REVOKE = "auto_revoke"
TV_ACTION_ADMIN_REVOKE = "admin_revoke"
TV_ACTION_UPDATE = "update"

TOWNLIT_VERIFICATION_ACTION_CHOICES = [
    (TV_ACTION_AUTO_AWARD, "Auto Award"),
    (TV_ACTION_ADMIN_GRANT, "Admin Grant"),
    (TV_ACTION_AUTO_REVOKE, "Auto Revoke"),
    (TV_ACTION_ADMIN_REVOKE, "Admin Revoke"),
    (TV_ACTION_UPDATE, "Update"),
]

TV_SOURCE_SYSTEM = "system"
TV_SOURCE_ADMIN = "admin"

TOWNLIT_VERIFICATION_SOURCE_CHOICES = [
    (TV_SOURCE_SYSTEM, "System"),
    (TV_SOURCE_ADMIN, "Admin"),
]