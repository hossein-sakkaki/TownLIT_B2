# apps/accounts/authentication.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-05.
# Last Update by Hossein Sakkaki on 2026-11-05.
#

"""JWT authentication with optional server-side session revocation."""

from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.accounts.services.session_generation_policy import (
    session_generation_from_payload,
    session_generation_matches,
)


class SessionGenerationJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        try:
            matches = session_generation_matches(
                user.pk,
                session_generation_from_payload(validated_token),
            )
        except Exception as exc:
            raise AuthenticationFailed(
                "Authentication is temporarily unavailable.",
                code="authentication_unavailable",
            ) from exc
        if not matches:
            raise AuthenticationFailed(
                "Session has expired. Please sign in again.",
                code="session_revoked",
            )
        return user
