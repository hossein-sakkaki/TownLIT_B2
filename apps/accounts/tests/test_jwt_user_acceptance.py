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
