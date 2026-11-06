# apps/accounts/services/session_jwt.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-05.
# Last Update by Hossein Sakkaki on 2026-11-05.
#

"""Emit the current per-account session generation in issued JWT pairs.

This step is *issuance only*. REST, refresh, and WebSocket enforcement
must not be enabled until every issuance and validation path is migrated.
"""

from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.services.session_security import get_session_generation


SESSION_GENERATION_CLAIM = "tl_sg"


def issue_session_refresh_token(user) -> RefreshToken:
    """Create a standard Simple JWT refresh token with its session version.

    The signed refresh token and the derived access token carry the same
    claim. Reading generation before minting fails closed on DB errors.
    Existing tokens lacking the claim remain valid until enforcement is
    intentionally enabled in a later stage.
    """
    if user is None or user.pk is None:
        raise ValueError("A persisted user is required for token issuance.")

    generation = get_session_generation(user.pk)
    refresh = RefreshToken.for_user(user)
    refresh[SESSION_GENERATION_CLAIM] = generation
    return refresh
