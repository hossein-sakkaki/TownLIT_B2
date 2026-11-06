# apps/accounts/serializers/session_refresh.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-05.
# Last Update by Hossein Sakkaki on 2026-11-05.
#

"""Reject previously revoked refresh tokens before rotating them."""

from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.settings import api_settings

from apps.accounts.services.session_generation_policy import (
    session_generation_enforced,
    session_generation_from_payload,
    session_generation_matches,
)


class SessionGenerationTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        if session_generation_enforced():
            # Authenticate the signed refresh token before trusting its claims.
            refresh = RefreshToken(attrs["refresh"])
            user_id = refresh.payload.get(api_settings.USER_ID_CLAIM)
            try:
                matches = session_generation_matches(
                    user_id,
                    session_generation_from_payload(refresh.payload),
                )
            except Exception as exc:
                raise InvalidToken("Session validation unavailable.") from exc
            if not matches:
                raise InvalidToken("Session has expired. Please sign in again.")
        return super().validate(attrs)
