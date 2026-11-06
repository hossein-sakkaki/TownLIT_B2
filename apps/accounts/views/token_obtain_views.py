# apps/accounts/views/token_obtain_views.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-05.
# Last Update by Hossein Sakkaki on 2026-11-05.
#

"""Protect the legacy Simple JWT token-issuance endpoint.

The canonical TownLIT auth flow is apps.accounts.views.auth_views.AuthViewSet.
Do not allow this generic compatibility endpoint to bypass account/2FA policy.
"""

from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.accounts.services.session_jwt import SESSION_GENERATION_CLAIM
from apps.accounts.services.session_security import get_session_generation
from apps.core.security.account_gate.service import is_restricted_owner_user


class TownLITTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        # TokenObtainPairSerializer calls get_token only after credentials
        # have been authenticated. Check security policy before minting a JWT.
        if getattr(user, "two_factor_enabled", False):
            raise AuthenticationFailed(
                "Two-factor authentication is required. Use TownLIT login."
            )

        if (
            not getattr(user, "is_active", False)
            or getattr(user, "is_deleted", False)
            or getattr(user, "is_suspended", False)
            or is_restricted_owner_user(user, fail_closed=True)
        ):
            raise AuthenticationFailed("Account access is unavailable.")

        token = super().get_token(user)
        token[SESSION_GENERATION_CLAIM] = get_session_generation(user.pk)
        return token


class TownLITTokenObtainPairView(TokenObtainPairView):
    serializer_class = TownLITTokenObtainPairSerializer
