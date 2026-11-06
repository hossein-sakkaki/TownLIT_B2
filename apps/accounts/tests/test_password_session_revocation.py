# apps/accounts/tests/test_password_session_revocation.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-05.
# Last Update by Hossein Sakkaki on 2026-11-05.
#

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import OperationalError
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.authentication import SessionGenerationJWTAuthentication
from apps.accounts.services.password_reset_tokens import issue_password_reset_token_v2
from apps.accounts.services.session_jwt import issue_session_refresh_token
from apps.accounts.services.session_security import get_session_generation
from apps.accounts.views.auth_views import AuthViewSet


@override_settings(AUTH_SESSION_GENERATION_ENFORCE=True,
                   AUTH_PASSWORD_SECURITY_V2_ENABLED=True)
class PasswordSessionRevocationTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = get_user_model().objects.create_user(
            email="password-session-revoke@example.com",
            password="ExistingPassword42!",
        )
        self.user.is_active = True
        self.user.save(update_fields=["is_active"])

    def _reset_link(self):
        token, stored = issue_password_reset_token_v2()
        self.user.reset_token = stored
        self.user.reset_token_expiration = timezone.now() + timedelta(minutes=30)
        self.user.save(update_fields=["reset_token", "reset_token_expiration"])
        return token

    def _reset(self, token, new_password="ReplacementPassword42!"):
        request = self.factory.post(
            f"/api/v1/accounts/auth/reset-password/{token}/",
            {"new_password": new_password}, format="json",
        )
        with patch.object(AuthViewSet, "get_throttles", return_value=[]):
            return AuthViewSet.as_view({"post": "reset_password"})(
                request, reset_token=token,
            )

    def _change(self, old_password="ExistingPassword42!",
                new_password="ReplacementPassword42!"):
        request = self.factory.post(
            "/api/v1/accounts/auth/change-password/",
            {"old_password": old_password, "new_password": new_password},
            format="json",
        )
        force_authenticate(request, user=self.user)
        with patch.object(AuthViewSet, "get_throttles", return_value=[]):
            return AuthViewSet.as_view({"post": "change_password"})(request)

    def test_reset_requires_fresh_login_and_revokes_prior_tokens(self):
        previous = issue_session_refresh_token(self.user)
        token = self._reset_link()
        result = self._reset(token)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data["login_required"], True)
        self.assertNotIn("access", result.data)
        self.assertNotIn("refresh", result.data)
        self.assertNotIn("user", result.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("ReplacementPassword42!"))
        self.assertEqual(get_session_generation(self.user.pk), 1)
        self.assertIsNone(self.user.reset_token)
        self.assertEqual(self._reset(token).status_code, 404)
        with self.assertRaises(Exception):
            SessionGenerationJWTAuthentication().get_user(previous.access_token)
        fresh = issue_session_refresh_token(self.user)
        self.assertEqual(fresh.access_token["tl_sg"], 1)
        self.assertEqual(
            SessionGenerationJWTAuthentication().get_user(fresh.access_token).pk,
            self.user.pk,
        )

    def test_reset_does_not_bypass_2fa(self):
        self.user.two_factor_enabled = True
        self.user.save(update_fields=["two_factor_enabled"])
        result = self._reset(self._reset_link())
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data["login_required"], True)
        self.assertNotIn("access", result.data)
        self.assertNotIn("refresh", result.data)

    def test_change_requires_login_and_revokes_prior_tokens(self):
        previous = issue_session_refresh_token(self.user)
        result = self._change()
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data["login_required"], True)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("ReplacementPassword42!"))
        self.assertEqual(get_session_generation(self.user.pk), 1)
        with self.assertRaises(Exception):
            SessionGenerationJWTAuthentication().get_user(previous.access_token)

    def test_wrong_current_password_does_not_revoke(self):
        result = self._change(old_password="IncorrectPassword42!")
        self.assertEqual(result.status_code, 400)
        self.assertEqual(get_session_generation(self.user.pk), 0)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("ExistingPassword42!"))

    def test_reusing_current_password_does_not_revoke(self):
        result = self._change(new_password="ExistingPassword42!")
        self.assertEqual(result.status_code, 400)
        self.assertEqual(get_session_generation(self.user.pk), 0)

    @override_settings(AUTH_SESSION_GENERATION_ENFORCE=False)
    def test_misconfigured_security_flag_rejects_reset_without_changes(self):
        token = self._reset_link()
        result = self._reset(token)
        self.assertEqual(result.status_code, 503)
        self.assertEqual(get_session_generation(self.user.pk), 0)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("ExistingPassword42!"))
        self.assertIsNotNone(self.user.reset_token)

    @override_settings(AUTH_SESSION_GENERATION_ENFORCE=False)
    def test_misconfigured_security_flag_rejects_change_without_changes(self):
        result = self._change()
        self.assertEqual(result.status_code, 503)
        self.assertEqual(get_session_generation(self.user.pk), 0)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("ExistingPassword42!"))

    @override_settings(AUTH_PASSWORD_SECURITY_V2_ENABLED=False)
    def test_legacy_reset_preserves_response_contract(self):
        result = self._reset(self._reset_link())
        self.assertEqual(result.status_code, 200)
        self.assertIn("access", result.data)
        self.assertIn("refresh", result.data)
        self.assertNotIn("login_required", result.data)
        self.assertEqual(get_session_generation(self.user.pk), 0)

    @override_settings(AUTH_PASSWORD_SECURITY_V2_ENABLED=False)
    def test_legacy_change_preserves_existing_session(self):
        result = self._change()
        self.assertEqual(result.status_code, 200)
        self.assertNotIn("login_required", result.data)
        self.assertEqual(get_session_generation(self.user.pk), 0)

    @patch("apps.accounts.views.auth_views.increment_session_generation",
           side_effect=OperationalError("session state unavailable"))
    def test_reset_database_failure_rolls_back_password_and_token(self, increment):
        token = self._reset_link()
        result = self._reset(token)
        # DRF's custom exception handler converts unhandled DB errors to HTTP 500.
        self.assertEqual(result.status_code, 500)
        self.assertNotIn("session state unavailable", str(result.data))
        increment.assert_called_once_with(self.user.pk)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("ExistingPassword42!"))
        self.assertIsNotNone(self.user.reset_token)
        self.assertEqual(get_session_generation(self.user.pk), 0)

    @patch("apps.accounts.views.auth_views.increment_session_generation",
           side_effect=OperationalError("session state unavailable"))
    def test_change_database_failure_rolls_back_password(self, increment):
        result = self._change()
        self.assertEqual(result.status_code, 500)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("ExistingPassword42!"))
        self.assertEqual(get_session_generation(self.user.pk), 0)
