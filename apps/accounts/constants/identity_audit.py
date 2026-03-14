# apps/accounts/constants/identity_audit.py

"""
Identity audit actions and sources.
"""

# Actions
IA_CREATE = "create"
IA_SUBMIT = "submit"
IA_VERIFY = "verify"
IA_REJECT = "reject"
IA_REVOKE = "revoke"
IA_UPDATE = "update"

IDENTITY_AUDIT_ACTION_CHOICES = [
    (IA_CREATE, "Create"),
    (IA_SUBMIT, "Submit"),
    (IA_VERIFY, "Verify"),
    (IA_REJECT, "Reject"),
    (IA_REVOKE, "Revoke"),
    (IA_UPDATE, "Update"),
]


# Sources
IA_SOURCE_VERIFF = "veriff"
IA_SOURCE_ORGANIZATION = "organization"
IA_SOURCE_ADMIN = "admin"
IA_SOURCE_SYSTEM = "system"

IDENTITY_AUDIT_SOURCE_CHOICES = [
    (IA_SOURCE_VERIFF, "Veriff"),
    (IA_SOURCE_ORGANIZATION, "Organization"),
    (IA_SOURCE_ADMIN, "Admin"),
    (IA_SOURCE_SYSTEM, "System"),
]