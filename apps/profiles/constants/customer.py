# apps/profiles/constants/customer.py

from django.utils.translation import gettext_lazy as _

# Customer deactivation reasons
CUSTOMER_USER_REQUEST = "user_request"
CUSTOMER_PAYMENT_ISSUE = "payment_issue"
CUSTOMER_ACCOUNT_SUSPENSION = "account_suspension"
CUSTOMER_INACTIVITY = "inactivity"
CUSTOMER_SECURITY_CONCERNS = "security_concerns"
CUSTOMER_VIOLATION_OF_TERMS = "violation_of_terms"
CUSTOMER_OTHER = "other"

CUSTOMER_DEACTIVATION_REASON_CHOICES = [
    (CUSTOMER_USER_REQUEST, _("User Request")),
    (CUSTOMER_PAYMENT_ISSUE, _("Payment Issue")),
    (CUSTOMER_ACCOUNT_SUSPENSION, _("Account Suspension")),
    (CUSTOMER_INACTIVITY, _("Inactivity")),
    (CUSTOMER_SECURITY_CONCERNS, _("Security Concerns")),
    (CUSTOMER_VIOLATION_OF_TERMS, _("Violation of Terms")),
    (CUSTOMER_OTHER, _("Other")),
]