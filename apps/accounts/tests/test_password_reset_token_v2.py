# apps/accounts/tests/test_password_reset_token_v2.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-05.
# Last Update by Hossein Sakkaki on 2026-11-05.
#

import datetime
import os
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from apps.accounts.services.password_reset_tokens import (
    issue_password_reset_token_v2,
    password_reset_lookup_value,
)
from apps.accounts.views.auth_views import AuthViewSet


class PasswordResetTokenV2Tests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = get_user_model().objects.create_user(
            email="passwordreset-v2@example.com",
            username="passwordreset_v2",
            password="PreviousPassword42!",
        )
        self.user.is_active = True
        self.user.save(update_fields=["is_active"])

    def _issue(self):
        request = self.factory.post(
            "/api/v1/accounts/auth/forget-password/",
            {"email": self.user.email},
            format="json",
        )
        with patch.dict(os.environ, {"PASSWORD_RESET_TOKEN_V2_ISSUE": "true"}), patch(
            "apps.accounts.views.auth_views.send_custom_email", return_value=True
        ) as send_email, patch.object(AuthViewSet, "get_throttles", return_value=[]):
            response = AuthViewSet.as_view({"post": "forget_password"})(request)
        self.assertEqual(response.status_code, 200)
        link = send_email.call_args.kwargs["context"]["reset_link"]
        return link.rstrip("/").split("/")[-1]

    def _reset(self, token, new_password="ReplacementPassword42!"):
        request = self.factory.post(
            f"/api/v1/accounts/auth/reset-password/{token}/",
            {"new_password": new_password},
            format="json",
        )
        with patch.object(AuthViewSet, "get_throttles", return_value=[]):
            return AuthViewSet.as_view({"post": "reset_password"})(
                request, reset_token=token
            )

    def test_issuance_defaults_to_legacy_until_flag_is_enabled(self):
        request = self.factory.post(
            "/api/v1/accounts/auth/forget-password/",
            {"email": self.user.email},
            format="json",
        )
        with patch.dict(os.environ, {"PASSWORD_RESET_TOKEN_V2_ISSUE": "false"}), patch(
            "apps.accounts.views.auth_views.send_custom_email", return_value=True
        ) as send_email, patch.object(AuthViewSet, "get_throttles", return_value=[]):
            response = AuthViewSet.as_view({"post": "forget_password"})(request)
        self.assertEqual(response.status_code, 200)
        bearer = send_email.call_args.kwargs["context"]["reset_link"].rstrip("/").split("/")[-1]
        self.user.refresh_from_db()
        self.assertEqual(self.user.reset_token, bearer)
        self.assertTrue(bearer.startswith("g"))

    def test_new_token_is_random_and_not_persisted_in_cleartext(self):
        first = self._issue()
        self.user.refresh_from_db()
        stored_first = self.user.reset_token
        self.assertTrue(first.startswith("r2_"))
        self.assertNotEqual(first, stored_first)
        self.assertEqual(password_reset_lookup_value(first), stored_first)
        self.assertNotIn(first, stored_first)
        second = self._issue()
        self.user.refresh_from_db()
        self.assertNotEqual(first, second)
        self.assertNotEqual(stored_first, self.user.reset_token)
        self.assertEqual(self._reset(first).status_code, 404)

    def test_new_token_roundtrip_once_then_replay_is_rejected(self):
        bearer = self._issue()
        self.assertEqual(self._reset(bearer).status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("ReplacementPassword42!"))
        self.assertIsNone(self.user.reset_token)
        self.assertIsNone(self.user.reset_token_expiration)
        self.assertEqual(self._reset(bearer).status_code, 404)

    def test_legacy_fernet_link_can_be_consumed(self):
        old_bearer = Fernet(settings.FERNET_KEY).encrypt(
            self.user.email.encode()
        ).decode()
        self.user.reset_token = old_bearer
        self.user.reset_token_expiration = timezone.now() + datetime.timedelta(minutes=10)
        self.user.save(update_fields=["reset_token", "reset_token_expiration"])
        self.assertEqual(self._reset(old_bearer).status_code, 200)

    def test_expired_and_missing_expiry_are_rejected(self):
        bearer = self._issue()
        for expiry in [timezone.now() - datetime.timedelta(seconds=1), None]:
            self.user.refresh_from_db()
            self.user.reset_token_expiration = expiry
            self.user.save(update_fields=["reset_token_expiration"])
            self.assertEqual(self._reset(bearer).status_code, 400)

    def test_invalid_format_is_not_accepted(self):
        self.assertIsNone(password_reset_lookup_value("r2_!"))
        self.assertIsNone(password_reset_lookup_value("a" * 256))
        self.assertEqual(self._reset("r2_!").status_code, 404)

    def test_v2_verifier_is_stable_and_unique_per_token(self):
        first, stored = issue_password_reset_token_v2()
        second, stored_other = issue_password_reset_token_v2()
        self.assertNotEqual(first, second)
        self.assertNotEqual(stored, stored_other)
        self.assertEqual(stored, password_reset_lookup_value(first))
        self.assertNotEqual(first, stored)
