# apps/accounts/tests/test_session_generation_enforcement.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-05.
# Last Update by Hossein Sakkaki on 2026-11-05.
#

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import OperationalError
from django.test import TestCase, override_settings
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.accounts.authentication import SessionGenerationJWTAuthentication
from apps.accounts.services.session_jwt import issue_session_refresh_token
from apps.accounts.services.session_security import increment_session_generation
from apps.accounts.services.session_generation_policy import (
    session_generation_matches,
)
from apps.core.websocket.access_auth import (
    validate_access_token_for_websocket,
    validate_legacy_websocket_session_access,
)


class SessionGenerationEnforcementTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="session-enforce@example.com", password="ExistingPassword42!"
        )
        self.user.is_active = True
        self.user.save(update_fields=["is_active"])
        self.client = APIClient()

    def _refresh(self, token):
        return self.client.post(
            "/api/token/refresh/", {"refresh": str(token)}, format="json"
        )

    @override_settings(AUTH_SESSION_GENERATION_ENFORCE=False)
    def test_enforcement_disabled_keeps_old_access_valid(self):
        old = issue_session_refresh_token(self.user).access_token
        increment_session_generation(self.user.pk)
        self.assertEqual(
            SessionGenerationJWTAuthentication().get_user(AccessToken(str(old))).pk,
            self.user.pk,
        )

    @override_settings(AUTH_SESSION_GENERATION_ENFORCE=False)
    def test_enforcement_disabled_keeps_old_refresh_valid(self):
        old = issue_session_refresh_token(self.user)
        increment_session_generation(self.user.pk)
        self.assertEqual(self._refresh(old).status_code, 200)

    @override_settings(AUTH_SESSION_GENERATION_ENFORCE=True)
    def test_current_access_is_accepted(self):
        increment_session_generation(self.user.pk)
        token = issue_session_refresh_token(self.user).access_token
        self.assertEqual(
            SessionGenerationJWTAuthentication().get_user(token).pk,
            self.user.pk,
        )

    @override_settings(AUTH_SESSION_GENERATION_ENFORCE=True)
    def test_revoked_access_is_rejected(self):
        old = issue_session_refresh_token(self.user).access_token
        increment_session_generation(self.user.pk)
        with self.assertRaises(AuthenticationFailed):
            SessionGenerationJWTAuthentication().get_user(old)

    @override_settings(AUTH_SESSION_GENERATION_ENFORCE=True)
    def test_revoked_refresh_is_rejected(self):
        old = issue_session_refresh_token(self.user)
        increment_session_generation(self.user.pk)
        self.assertEqual(self._refresh(old).status_code, 401)

    @override_settings(AUTH_SESSION_GENERATION_ENFORCE=True)
    def test_current_refresh_still_rotates(self):
        increment_session_generation(self.user.pk)
        current = issue_session_refresh_token(self.user)
        response = self._refresh(current)
        self.assertEqual(response.status_code, 200)
        self.assertIn("refresh", response.data)
        self.assertEqual(RefreshToken(response.data["refresh"])["tl_sg"], 1)

    @override_settings(AUTH_SESSION_GENERATION_ENFORCE=True)
    def test_legacy_zero_access_accepted_before_first_revocation(self):
        old = RefreshToken.for_user(self.user).access_token
        self.assertEqual(
            SessionGenerationJWTAuthentication().get_user(old).pk,
            self.user.pk,
        )

    @override_settings(AUTH_SESSION_GENERATION_ENFORCE=True)
    def test_legacy_zero_refresh_accepted_before_first_revocation(self):
        old = RefreshToken.for_user(self.user)
        self.assertEqual(self._refresh(old).status_code, 200)

    @override_settings(AUTH_SESSION_GENERATION_ENFORCE=True)
    def test_legacy_access_rejected_after_revocation(self):
        old = RefreshToken.for_user(self.user).access_token
        increment_session_generation(self.user.pk)
        with self.assertRaises(AuthenticationFailed):
            SessionGenerationJWTAuthentication().get_user(old)

    @override_settings(AUTH_SESSION_GENERATION_ENFORCE=True)
    def test_legacy_refresh_rejected_after_revocation(self):
        old = RefreshToken.for_user(self.user)
        increment_session_generation(self.user.pk)
        self.assertEqual(self._refresh(old).status_code, 401)

    @override_settings(AUTH_SESSION_GENERATION_ENFORCE=True)
    def test_malformed_generation_is_denied(self):
        self.assertFalse(session_generation_matches(self.user.pk, "0"))
        self.assertFalse(session_generation_matches(self.user.pk, -1))
        self.assertFalse(session_generation_matches(self.user.pk, True))

    @override_settings(AUTH_SESSION_GENERATION_ENFORCE=True)
    def test_database_failure_does_not_accept_token(self):
        token = issue_session_refresh_token(self.user).access_token
        with patch(
            "apps.accounts.services.session_generation_policy.get_session_generation",
            side_effect=OperationalError("database unavailable"),
        ):
            with self.assertRaises(AuthenticationFailed):
                SessionGenerationJWTAuthentication().get_user(token)

    @override_settings(AUTH_SESSION_GENERATION_ENFORCE=True)
    def test_websocket_v2_handshake_rejects_revoked_generation(self):
        old = issue_session_refresh_token(self.user).access_token
        increment_session_generation(self.user.pk)
        self.assertIsNone(validate_access_token_for_websocket(str(old)))

    @override_settings(AUTH_SESSION_GENERATION_ENFORCE=True)
    def test_websocket_v2_current_generation_is_allowed(self):
        current = issue_session_refresh_token(self.user).access_token
        self.assertEqual(
            validate_access_token_for_websocket(str(current)).pk, self.user.pk
        )

    @override_settings(AUTH_SESSION_GENERATION_ENFORCE=True)
    def test_legacy_websocket_policy_rejects_old_claim_after_revocation(self):
        old = issue_session_refresh_token(self.user).access_token
        increment_session_generation(self.user.pk)
        self.assertFalse(session_generation_matches(self.user.pk, old["tl_sg"]))

    @override_settings(AUTH_SESSION_GENERATION_ENFORCE=True)
    def test_legacy_websocket_current_generation_is_allowed(self):
        self.assertTrue(
            validate_legacy_websocket_session_access(self.user.pk, 0)
        )

    @override_settings(AUTH_SESSION_GENERATION_ENFORCE=True)
    def test_legacy_websocket_rejects_generation_after_increment(self):
        increment_session_generation(self.user.pk)
        self.assertFalse(
            validate_legacy_websocket_session_access(self.user.pk, 0)
        )

    @override_settings(AUTH_SESSION_GENERATION_ENFORCE=True)
    def test_legacy_websocket_rechecks_account_deactivation(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.assertFalse(
            validate_legacy_websocket_session_access(self.user.pk, 0)
        )

    def test_runtime_wiring_is_explicit(self):
        from django.conf import settings
        self.assertEqual(
            settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"][0],
            "apps.accounts.authentication.SessionGenerationJWTAuthentication",
        )
        self.assertEqual(
            settings.SIMPLE_JWT["TOKEN_REFRESH_SERIALIZER"],
            "apps.accounts.serializers.session_refresh.SessionGenerationTokenRefreshSerializer",
        )
