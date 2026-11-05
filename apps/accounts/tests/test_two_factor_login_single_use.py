# apps/accounts/tests/test_two_factor_login_single_use.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-05.
# Last Update by Hossein Sakkaki on 2026-11-05.
#

"""Regression coverage for the existing 2FA login API contract."""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from apps.accounts.views.auth_views import AuthViewSet


class TwoFactorLoginSingleUseTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = get_user_model().objects.create_user(
            email="single-use-2fa@example.com",
            username="single_use_2fa",
            password="ExistingPassword42!",
        )
        self.user.is_active = True
        self.user.two_factor_enabled = True
        self.user.save(update_fields=["is_active", "two_factor_enabled"])

    def _login_with_2fa(self, code):
        request = self.factory.post(
            "/api/v1/accounts/auth/login-with-2fa/",
            {"email": self.user.email, "otp_code": code},
            format="json",
        )
        with patch.object(AuthViewSet, "get_throttles", return_value=[]):
            return AuthViewSet.as_view({"post": "login_with_2fa"})(request)

    def test_valid_otp_issues_tokens_once_and_is_cleared(self):
        code = self.user.generate_two_factor_token()
        first = self._login_with_2fa(code)
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.data["access"])
        self.assertTrue(first.data["refresh"])

        self.user.refresh_from_db()
        self.assertIsNone(self.user.two_factor_token)
        self.assertIsNone(self.user.two_factor_token_expiry)
        self.assertIsNotNone(self.user.last_login)

        second = self._login_with_2fa(code)
        self.assertEqual(second.status_code, 400)
        self.assertNotIn("access", second.data)
        self.assertNotIn("refresh", second.data)

    def test_wrong_otp_does_not_consume_correct_code(self):
        code = self.user.generate_two_factor_token()
        wrong_code = "000000" if code != "000000" else "111111"
        wrong = self._login_with_2fa(wrong_code)
        self.assertEqual(wrong.status_code, 400)
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.two_factor_token)
        self.assertEqual(self._login_with_2fa(code).status_code, 200)

    def test_expired_otp_does_not_issue_session(self):
        code = self.user.generate_two_factor_token()
        self.user.two_factor_token_expiry = timezone.now() - timedelta(seconds=1)
        self.user.save(update_fields=["two_factor_token_expiry"])
        result = self._login_with_2fa(code)
        self.assertEqual(result.status_code, 400)
        self.assertNotIn("access", result.data)

    def test_malformed_otp_rejected_without_bcrypt(self):
        with patch.object(
            get_user_model(), "validate_two_factor_token",
            side_effect=AssertionError("bcrypt should not run"),
        ):
            result = self._login_with_2fa("x" * 600)
        self.assertEqual(result.status_code, 400)
        self.assertNotIn("access", result.data)

    def test_suspended_account_cannot_consume_otp(self):
        code = self.user.generate_two_factor_token()
        self.user.is_suspended = True
        self.user.save(update_fields=["is_suspended"])
        result = self._login_with_2fa(code)
        self.assertEqual(result.status_code, 423)
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.two_factor_token)
        self.assertNotIn("access", result.data)

    def test_inactive_account_cannot_consume_otp(self):
        code = self.user.generate_two_factor_token()
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        result = self._login_with_2fa(code)
        self.assertEqual(result.status_code, 403)
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.two_factor_token)
        self.assertNotIn("access", result.data)
