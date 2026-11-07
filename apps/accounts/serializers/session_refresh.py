# apps/accounts/serializers/session_refresh.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-05.
# Last Update by Hossein Sakkaki on 2026-11-07.
#

"""Validate the signed refresh identity and current session before rotation."""

from django.contrib.auth import get_user_model
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.services.session_generation_policy import (
    session_generation_enforced,
    session_generation_from_payload,
    session_generation_matches,
)

# CustomUser.id is a BigAutoField: positive, signed 64-bit on MySQL/SQLite.
_MAX_REFRESH_USER_ID = 2**63 - 1


def _verified_refresh_user_id(claim) -> int:
    """Normalize only a previously signature-verified refresh claim.

    SimpleJWT 5.3.1 emits integers; 5.5.1 emits decimal strings. This is a
    local refresh adapter, never a general identity/session validator. Bound
    strings before int() and accept no aliases, Unicode digits or overflow.
    """
    if (
        type(claim) is str
        and 1 <= len(claim) <= 19
        and claim.isascii()
        and claim.isdecimal()
        and claim[0] != "0"
    ):
        claim = int(claim)
    if type(claim) is not int or not 1 <= claim <= _MAX_REFRESH_USER_ID:
        raise InvalidToken("Token contained no valid user identification.")
    return claim


class SessionGenerationTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        try:
            # Verify signature, expiry, refresh type and blacklist FIRST. Never
            # normalize an unverified request value or rewrite the wire claim.
            refresh = RefreshToken(attrs["refresh"])
            user_id = _verified_refresh_user_id(
                refresh.payload.get(api_settings.USER_ID_CLAIM)
            )
            User = get_user_model()
            user = User.objects.get(**{api_settings.USER_ID_FIELD: user_id})
            # 5.3.1 lacks the parent's current-user check. Require an available,
            # active account in both profiles, including with enforcement off.
            # Soft deletion/reactivation, suspension/logout and restricted-owner
            # access remain governed by their existing action/account gates.
            # Refresh identity alone does not authorize a protected API/WS action.
            if not user.is_active or not api_settings.USER_AUTHENTICATION_RULE(user):
                raise InvalidToken("Account access is unavailable.")
            if session_generation_enforced() and not session_generation_matches(
                user.pk,
                session_generation_from_payload(refresh.payload),
            ):
                raise InvalidToken("Session has expired. Please sign in again.")
            # Keep upstream user checks, rotation, outstanding and blacklist
            # semantics intact. The normalized ID above is local only.
            return super().validate(attrs)
        except (InvalidToken, TokenError):
            raise
        except Exception as exc:
            # Missing accounts and DB/policy failures must never mint tokens,
            # including failures in the parent's current-user/rotation checks.
            raise InvalidToken("Session validation unavailable.") from exc
