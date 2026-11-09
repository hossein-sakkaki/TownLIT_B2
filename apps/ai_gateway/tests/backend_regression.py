# apps/ai_gateway/tests/backend_regression.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-09.
#

"""Run explicitly with the backend profile; never part of the small core suite."""

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import resolve
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIClient

from apps.accounts.authentication import SessionGenerationJWTAuthentication
from apps.accounts.services.session_jwt import issue_session_refresh_token
from apps.accounts.services.session_security import increment_session_generation


class BackendRegressionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="b1-synthetic@example.invalid",
            password="SyntheticPassword42!",
        )
        self.user.is_active = True
        self.user.is_superuser = True
        self.user.save(update_fields=["is_active", "is_superuser"])

    @override_settings(AI_GATEWAY_ENABLED=True)
    def test_human_jwt_and_session_never_authorize_gateway(self):
        client = APIClient()
        token = issue_session_refresh_token(self.user)
        client.credentials(HTTP_AUTHORIZATION="Bearer " + str(token.access_token))
        self.assertEqual(
            client.get("/api/v1/ai-integrations/capabilities/").status_code, 503
        )
        client.credentials()
        client.force_login(self.user)
        self.assertEqual(
            client.get("/api/v1/ai-integrations/capabilities/").status_code, 503
        )

    def test_0105_table_and_human_generation_revocation(self):
        executor = MigrationExecutor(connection)
        self.assertIn(
            ("accounts", "0105_user_auth_session_state"),
            executor.loader.applied_migrations,
        )
        self.assertEqual(
            executor.migration_plan(executor.loader.graph.leaf_nodes()), []
        )
        self.assertIn(
            "accounts_userauthsessionstate", connection.introspection.table_names()
        )
        token = issue_session_refresh_token(self.user).access_token
        self.assertEqual(token["tl_sg"], 0)
        increment_session_generation(self.user.pk)
        with override_settings(AUTH_SESSION_GENERATION_ENFORCE=True):
            with self.assertRaises(AuthenticationFailed):
                SessionGenerationJWTAuthentication().get_user(token)

    @override_settings(AUTH_SESSION_GENERATION_ENFORCE=True)
    def test_refresh_rotation_preserves_checkpoint_encrypted_identity(self):
        from apps.core.websocket.access_auth import validate_access_token_for_websocket

        before = (self.user.email_encrypted, self.user.email_blind_index)
        for claim_type in (int, str):
            with self.subTest(claim_type=claim_type):
                token = issue_session_refresh_token(self.user)
                token["user_id"] = claim_type(self.user.pk)
                response = APIClient().post(
                    "/api/token/refresh/", {"refresh": str(token)}, format="json"
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    validate_access_token_for_websocket(response.data["access"]).pk,
                    self.user.pk,
                )
                self.assertEqual(
                    APIClient()
                    .post("/api/token/refresh/", {"refresh": str(token)}, format="json")
                    .status_code,
                    401,
                )
        self.user.refresh_from_db()
        self.assertEqual(
            before, (self.user.email_encrypted, self.user.email_blind_index)
        )
        self.assertEqual(self.user.email, "b1-synthetic@example.invalid")

    def test_checkpoint_0114_migration_and_encrypted_only_email_are_preserved(self):
        executor = MigrationExecutor(connection)
        self.assertEqual(
            executor.loader.graph.leaf_nodes("accounts"),
            [("accounts", "0114_email_encrypted_only_cutover")],
        )
        self.assertIn(
            ("accounts", "0114_email_encrypted_only_cutover"),
            executor.loader.applied_migrations,
        )
        with connection.cursor() as cursor:
            columns = {
                column.name
                for column in connection.introspection.get_table_description(
                    cursor, get_user_model()._meta.db_table
                )
            }
        self.assertNotIn("email", columns)
        self.assertTrue({"email_encrypted", "email_blind_index"} <= columns)

    def test_human_and_business_routes_remain_on_existing_views(self):
        self.assertEqual(
            resolve("/api/token/").func.view_class.__name__,
            "TownLITTokenObtainPairView",
        )
        self.assertEqual(
            resolve("/api/token/refresh/").func.view_class.__name__, "TokenRefreshView"
        )
        self.assertEqual(
            resolve("/api/v1/accounting/dashboard/").func.view_class.__name__,
            "AccountingDashboardView",
        )
        from apps.core.websocket.routing import websocket_urlpatterns

        patterns = " ".join(str(route.pattern) for route in websocket_urlpatterns)
        self.assertIn("v2", patterns)
        self.assertIn("ws/", patterns)

    @override_settings(AI_GATEWAY_ENABLED=True)
    def test_denied_requests_leave_all_domain_records_unchanged(self):
        from apps.advancement.models.external_entity import ExternalEntity

        ExternalEntity.objects.create(
            name="Synthetic B1 fixture", entity_type="FOUNDATION", country="CA"
        )
        models = [
            model
            for app in ("accounting", "advancement")
            for model in apps.get_app_config(app).get_models()
        ]

        def snapshot():
            return {
                model._meta.label: list(model.objects.order_by("pk").values())
                for model in models
            }

        before = snapshot()
        with CaptureQueriesContext(connection) as queries:
            for path in (
                "accounting/vendors/",
                "accounting/document-intakes/",
                "accounting/bank-lines/",
                "advancement/opportunities/",
            ):
                for method in (self.client.get, self.client.post):
                    self.assertEqual(
                        method("/api/v1/ai-integrations/" + path).status_code, 503
                    )
        self.assertEqual(before, snapshot())
        self.assertFalse(
            any(
                "accounting_" in q["sql"].lower() or "advancement_" in q["sql"].lower()
                for q in queries
            )
        )

    def test_isolated_encrypted_field_and_storage(self):
        from django.core.files.storage import storages
        from django.db import models
        from django_cryptography.fields import encrypt

        field = encrypt(models.TextField())
        field.set_attributes_from_name("synthetic")
        value = field.get_db_prep_value("synthetic-secret", connection)
        self.assertNotEqual(value, "synthetic-secret")
        self.assertEqual(
            field.from_db_value(value, None, connection), "synthetic-secret"
        )
        self.assertEqual(storages["default"].__class__.__name__, "InMemoryStorage")
