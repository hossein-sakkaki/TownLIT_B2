# apps/accounts/services/password_session_policy.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-05.
# Last Update by Hossein Sakkaki on 2026-11-05.
#

"""Feature gate for coordinated, atomic password-driven JWT revocation.

This gate is deliberately independent of the session-generation gate.
Enabling secure password mutations before the enforcement gate is active
would revoke nothing; return a service-unavailable response instead.
"""

from django.conf import settings

from apps.accounts.services.session_generation_policy import (
    session_generation_enforced,
)


def password_security_v2_enabled() -> bool:
    return bool(getattr(settings, "AUTH_PASSWORD_SECURITY_V2_ENABLED", False))


def password_security_v2_ready() -> bool:
    return password_security_v2_enabled() and session_generation_enforced()
