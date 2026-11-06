# apps/accounts/tests/test_session_jwt_issuance.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-05.
# Last Update by Hossein Sakkaki on 2026-11-05.
#

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import OperationalError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.accounts.services.session_jwt import (
    SESSION_GENERATION_CLAIM,
    issue_session_refresh_token,
)
from apps.accounts.services.session_security import increment_session_generation
from apps.accounts.views.token_obtain_views import TownLITTokenObtainPairSerializer


class SessionJWTIssuanceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="session-jwt-issuance@example.com",
            password="ExistingPassword42!",
        )
        # CustomUser.is_active defaults to False; the legacy serializer
        # correctly refuses to issue tokens for inactive accounts.
        self.user.is_active = True
        self.user.save(update_fields=["is_active"])
        self.client = APIClient()

    def test_generation_zero_added_without_creating_state_row(self):
        refresh = issue_session_refresh_token(self.user)
        self.assertEqual(refresh[SESSION_GENERATION_CLAIM], 0)
        self.assertEqual(refresh.access_token[SESSION_GENERATION_CLAIM], 0)

    def test_new_issuance_inherits_incremented_generation(self):
        old_token = issue_session_refresh_token(self.user)
        increment_session_generation(self.user.pk)
        new_token = issue_session_refresh_token(self.user)
        self.assertEqual(old_token[SESSION_GENERATION_CLAIM], 0)
        self.assertEqual(new_token[SESSION_GENERATION_CLAIM], 1)
        self.assertEqual(new_token.access_token[SESSION_GENERATION_CLAIM], 1)

    def test_legacy_obtain_serializer_adds_current_generation(self):
        increment_session_generation(self.user.pk)
        token = TownLITTokenObtainPairSerializer.get_token(self.user)
        self.assertEqual(token[SESSION_GENERATION_CLAIM], 1)
        self.assertEqual(token.access_token[SESSION_GENERATION_CLAIM], 1)

    def test_rotated_refresh_preserves_generation_claim(self):
        increment_session_generation(self.user.pk)
        refresh = issue_session_refresh_token(self.user)
        response = self.client.post(
            "/api/token/refresh/",
            {"refresh": str(refresh)},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        access = AccessToken(response.data["access"])
        rotated = RefreshToken(response.data["refresh"])
        self.assertEqual(access[SESSION_GENERATION_CLAIM], 1)
        self.assertEqual(rotated[SESSION_GENERATION_CLAIM], 1)

    def test_unmodified_legacy_token_still_refreshes_before_enforcement(self):
        previous_refresh = RefreshToken.for_user(self.user)
        self.assertNotIn(SESSION_GENERATION_CLAIM, previous_refresh.payload)
        response = self.client.post(
            "/api/token/refresh/",
            {"refresh": str(previous_refresh)},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

    def test_generation_lookup_failure_prevents_token_issuance(self):
        with patch(
            "apps.accounts.services.session_jwt.get_session_generation",
            side_effect=OperationalError("database unavailable"),
        ):
            with self.assertRaises(OperationalError):
                issue_session_refresh_token(self.user)

    def test_issuer_rejects_unsaved_user(self):
        user = get_user_model()(email="unsaved@example.com")
        with self.assertRaises(ValueError):
            issue_session_refresh_token(user)
