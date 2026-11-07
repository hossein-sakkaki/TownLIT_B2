# apps/accounts/tests/test_jwt_user_acceptance.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-07.
# Last Update by Hossein Sakkaki on 2026-11-07.
#

"""Explicit compatibility deltas; passing does not approve release policy."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import OperationalError, connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

from apps.accounts.serializers.session_refresh import (
    SessionGenerationTokenRefreshSerializer,
)
from apps.accounts.services.session_jwt import issue_session_refresh_token


@override_settings(AUTH_SESSION_GENERATION_ENFORCE=False)
class RefreshAvailabilityAcceptanceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="jwt-availability@example.invalid", password="SyntheticPassword42!"
        )
        self.user.is_active = True
        self.user.save(update_fields=["is_active"])

    def test_lookup_outage_denies_even_when_generation_enforcement_is_off(self):
        token = issue_session_refresh_token(self.user)
        with patch.object(
            get_user_model().objects,
            "get",
            side_effect=OperationalError("synthetic unavailable"),
        ):
            response = APIClient().post(
                "/api/token/refresh/", {"refresh": str(token)}, format="json"
            )
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("refresh", response.data)
        self.assertNotIn("access", response.data)
        self.assertFalse(
            BlacklistedToken.objects.filter(token__jti=token["jti"]).exists()
        )

    def test_unenforced_valid_refresh_adds_one_user_and_one_blacklist_read(self):
        parent_token = issue_session_refresh_token(self.user)
        with CaptureQueriesContext(connection) as parent_queries:
            parent = TokenRefreshSerializer().validate({"refresh": str(parent_token)})
        self.assertIn("refresh", parent)
        guarded_token = issue_session_refresh_token(self.user)
        with CaptureQueriesContext(connection) as guarded_queries:
            guarded = SessionGenerationTokenRefreshSerializer().validate(
                {"refresh": str(guarded_token)}
            )
        self.assertIn("refresh", guarded)
        table = get_user_model()._meta.db_table

        def user_reads(queries):
            return sum(
                query["sql"].startswith("SELECT") and table in query["sql"]
                for query in queries
            )

        self.assertEqual(user_reads(guarded_queries), user_reads(parent_queries) + 1)
        self.assertEqual(len(guarded_queries), len(parent_queries) + 2)

    def _auth_request(self, action, data, *, authenticate=False):
        from rest_framework.test import APIRequestFactory, force_authenticate

        from apps.accounts.views.auth_views import AuthViewSet

        request = APIRequestFactory().post("/synthetic/auth/", data, format="json")
        if authenticate:
            force_authenticate(request, user=self.user)
        with patch.object(AuthViewSet, "get_throttles", return_value=[]):
            return AuthViewSet.as_view({"post": action})(request)

    def test_canonical_password_login_preserves_numeric_api_user_id(self):
        from rest_framework_simplejwt.tokens import RefreshToken

        from apps.profiles.models.guest import GuestUser

        GuestUser.objects.create(user=self.user)
        response = self._auth_request(
            "login", {"identifier": self.user.email, "password": "SyntheticPassword42!"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIs(type(response.data["user_id"]), int)
        self.assertEqual(response.data["user_id"], self.user.pk)
        self.assertEqual(RefreshToken(response.data["refresh"])["tl_sg"], 0)

    def test_canonical_login_starts_2fa_without_issuing_credentials(self):
        self.user.two_factor_enabled = True
        self.user.save(update_fields=["two_factor_enabled"])
        with patch(
            "apps.accounts.views.auth_views.send_custom_email", return_value=True
        ):
            response = self._auth_request(
                "login",
                {"identifier": self.user.username, "password": "SyntheticPassword42!"},
            )
        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.data["two_factor_enabled"])
        self.assertEqual(response.data["email"], self.user.email)
        self.assertFalse("access" in response.data or "refresh" in response.data)

    def test_logout_is_idempotent_and_does_not_claim_all_session_revocation(self):
        from rest_framework_simplejwt.tokens import AccessToken

        from apps.accounts.authentication import SessionGenerationJWTAuthentication
        from apps.accounts.services.session_security import get_session_generation

        submitted = issue_session_refresh_token(self.user)
        sibling = issue_session_refresh_token(self.user)
        with patch(
            "apps.accounts.views.auth_views.release_user_device_push_ownership",
            return_value=0,
        ):
            first = self._auth_request(
                "logout", {"refresh": str(submitted)}, authenticate=True
            )
            retry = self._auth_request(
                "logout", {"refresh": str(submitted)}, authenticate=True
            )
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.data["token_revoked"])
        self.assertEqual(retry.status_code, 200)
        client = APIClient()
        self.assertEqual(
            client.post(
                "/api/token/refresh/", {"refresh": str(submitted)}, format="json"
            ).status_code,
            401,
        )
        self.assertEqual(
            client.post(
                "/api/token/refresh/", {"refresh": str(sibling)}, format="json"
            ).status_code,
            200,
        )
        self.assertEqual(
            SessionGenerationJWTAuthentication()
            .get_user(AccessToken(str(submitted.access_token)))
            .pk,
            self.user.pk,
        )
        self.assertEqual(get_session_generation(self.user.pk), 0)
