# apps/accounts/services/session_generation_policy.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-05.
# Last Update by Hossein Sakkaki on 2026-11-05.
#

"""Optional, fail-closed JWT session generation comparison.

Legacy signed tokens without the tl_sg claim have generation zero. They are
accepted while the stored generation is zero, but rejected after revocation.
Do not cache generation lookups: password revocation must take effect on the
next authentication/refresh/revalidation check.
"""

from django.conf import settings

from apps.accounts.services.session_jwt import SESSION_GENERATION_CLAIM
from apps.accounts.services.session_security import get_session_generation


def session_generation_enforced() -> bool:
    return bool(getattr(settings, "AUTH_SESSION_GENERATION_ENFORCE", False))


def session_generation_matches(user_id, token_claim) -> bool:
    """Compare a signed token claim with authoritative DB state.

    Raise database exceptions to the caller, which must deny authorization.
    An absent claim is accepted only for generation-zero accounts.
    """
    if not session_generation_enforced():
        return True
    if not isinstance(user_id, int) or isinstance(user_id, bool) or user_id <= 0:
        return False
    if token_claim is None:
        token_generation = 0
    elif isinstance(token_claim, int) and not isinstance(token_claim, bool) and token_claim >= 0:
        token_generation = token_claim
    else:
        return False
    return token_generation == get_session_generation(user_id)


def session_generation_from_payload(payload):
    """Extract the optional generation claim from a verified token payload."""
    return payload.get(SESSION_GENERATION_CLAIM)
