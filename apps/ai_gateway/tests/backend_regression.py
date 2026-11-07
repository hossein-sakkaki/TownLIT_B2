# apps/ai_gateway/tests/backend_regression.py
# TownLIT-Backend
# Created by Codex on 2026-11-06.
# Last Update by Codex on 2026-11-06.

"""Run explicitly with the backend profile; never part of the small core suite."""

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection
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
            email="b1-synthetic@example.invalid", password="SyntheticPassword42!",
        )
        self.user.is_active = True
        self.user.is_superuser = True
        self.user.save(update_fields=["is_active", "is_superuser"])

    @override_settings(AI_GATEWAY_ENABLED=True)
    def test_human_jwt_and_session_never_authorize_gateway(self):
        client = APIClient()
        token = issue_session_refresh_token(self.user)
        client.credentials(HTTP_AUTHORIZATION="Bearer " + str(token.access_token))
        self.assertEqual(client.get("/api/v1/ai-integrations/capabilities/").status_code, 503)
        client.credentials()
        client.force_login(self.user)
        self.assertEqual(client.get("/api/v1/ai-integrations/capabilities/").status_code, 503)

    def test_0105_table_and_human_generation_revocation(self):
        self.assertIn("accounts_userauthsessionstate", connection.introspection.table_names())
        token = issue_session_refresh_token(self.user).access_token
        self.assertEqual(token["tl_sg"], 0)
        increment_session_generation(self.user.pk)
        with override_settings(AUTH_SESSION_GENERATION_ENFORCE=True):
            with self.assertRaises(AuthenticationFailed):
                SessionGenerationJWTAuthentication().get_user(token)

    def test_human_and_business_routes_remain_on_existing_views(self):
        self.assertEqual(resolve("/api/token/").func.view_class.__name__, "TownLITTokenObtainPairView")
        self.assertEqual(resolve("/api/token/refresh/").func.view_class.__name__, "TokenRefreshView")
        self.assertEqual(resolve("/api/v1/accounting/dashboard/").func.view_class.__name__, "AccountingDashboardView")
        from apps.core.websocket.routing import websocket_urlpatterns
        patterns = " ".join(str(route.pattern) for route in websocket_urlpatterns)
        self.assertIn("v2", patterns)
        self.assertIn("ws/", patterns)

    @override_settings(AI_GATEWAY_ENABLED=True)
    def test_denied_requests_leave_all_domain_records_unchanged(self):
        from apps.advancement.models.external_entity import ExternalEntity
        ExternalEntity.objects.create(name="Synthetic B1 fixture", entity_type="FOUNDATION", country="CA")
        models = [model for app in ("accounting", "advancement")
                  for model in apps.get_app_config(app).get_models()]

        def snapshot():
            return {model._meta.label: list(model.objects.order_by("pk").values()) for model in models}

        before = snapshot()
        with CaptureQueriesContext(connection) as queries:
            for path in ("accounting/vendors/", "accounting/document-intakes/",
                         "accounting/bank-lines/", "advancement/opportunities/"):
                for method in (self.client.get, self.client.post):
                    self.assertEqual(method("/api/v1/ai-integrations/" + path).status_code, 503)
        self.assertEqual(before, snapshot())
        self.assertFalse(any("accounting_" in q["sql"].lower() or "advancement_" in q["sql"].lower()
                             for q in queries))

    def test_isolated_encrypted_field_and_storage(self):
        from django.core.files.storage import storages
        from django_cryptography.fields import encrypt
        from django.db import models
        field = encrypt(models.TextField())
        field.set_attributes_from_name("synthetic")
        value = field.get_db_prep_value("synthetic-secret", connection)
        self.assertNotEqual(value, "synthetic-secret")
        self.assertEqual(field.from_db_value(value, None, connection), "synthetic-secret")
        self.assertEqual(storages["default"].__class__.__name__, "InMemoryStorage")
