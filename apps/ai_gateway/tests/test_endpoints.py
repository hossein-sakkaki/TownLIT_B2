# apps/ai_gateway/tests/test_endpoints.py
# TownLIT-Backend
# Created by Codex on 2026-11-06.
# Last Update by Codex on 2026-11-06.

from unittest.mock import patch
from uuid import UUID

from django.test import Client, SimpleTestCase, override_settings

from apps.ai_gateway.security import UnavailableSecurity


class DenialTests(SimpleTestCase):
    def test_every_path_and_method_denied_without_database_or_identity(self):
        for enabled in (False, True, "true", None):
            with override_settings(AI_GATEWAY_ENABLED=enabled):
                for path in ("", "token/", "capabilities/", "accounting/vendors/",
                             "advancement/opportunities/", "arbitrary/model/"):
                    for method in ("get", "post", "put", "patch", "delete", "head", "options"):
                        with self.subTest(enabled=enabled, path=path, method=method):
                            response = getattr(self.client, method)(
                                "/api/v1/ai-integrations/" + path,
                                HTTP_AUTHORIZATION="Bearer synthetic-secret",
                                HTTP_X_AGENT_ID="micah",
                                HTTP_X_SSL_CLIENT_VERIFY="SUCCESS",
                                HTTP_X_CLIENT_CERT="forged",
                            )
                            self.assertEqual(response.status_code, 503)
                            self.assertEqual(response["Cache-Control"], "no-store")
                            if method != "head":
                                data = response.json()
                                self.assertEqual(data["error"]["code"],
                                                 "security_unavailable" if enabled is True else "gateway_disabled")
                                UUID(data["request_id"])
                                self.assertNotIn("synthetic-secret", response.content.decode())

    @override_settings(AI_GATEWAY_ENABLED=True)
    def test_security_and_audit_outage_remain_denied_and_redacted(self):
        for target in ("apps.ai_gateway.views.UnavailableSecurity.verify",
                       "apps.ai_gateway.views.log_denial"):
            with patch(target, side_effect=RuntimeError("private-error")):
                response = self.client.get("/api/v1/ai-integrations/capabilities/")
                self.assertEqual(response.status_code, 503)
                self.assertNotIn(b"private-error", response.content)

    def test_csrf_is_not_exempted(self):
        response = Client(enforce_csrf_checks=True).post("/api/v1/ai-integrations/token/")
        self.assertEqual(response.status_code, 403)

    def test_all_verification_and_issuance_unavailable(self):
        for method in ("verify", "issue"):
            with self.assertRaisesMessage(Exception, "security_unavailable"):
                getattr(UnavailableSecurity(), method)("synthetic")
