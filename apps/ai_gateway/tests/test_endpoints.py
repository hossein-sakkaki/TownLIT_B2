# apps/ai_gateway/tests/test_endpoints.py
# TownLIT-Backend
# Created by Codex on 2026-11-06.
# Last Update by Codex on 2026-11-06.

from unittest.mock import patch
from uuid import UUID

from django.test import Client, RequestFactory, SimpleTestCase, override_settings

from apps.ai_gateway.security import UnavailableSecurity
from apps.ai_gateway.views import denied_endpoint


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

    @override_settings(AI_GATEWAY_ENABLED=True)
    def test_human_superuser_and_tampered_transport_still_denied(self):
        from types import SimpleNamespace

        for method, path, body in (("GET", "/capabilities/?scope=all", b""),
                                   ("POST", "/accounting/post/", b'{"is_staff":true}'),
                                   ("PATCH", "/advancement/opportunities/", b"tampered")):
            request = RequestFactory().generic(method, path, body,
                                               HTTP_SIGNATURE="synthetic-forged",
                                               HTTP_CONTENT_DIGEST="sha-256=:forged:")
            request.user = SimpleNamespace(is_authenticated=True, is_staff=True, is_superuser=True)
            response = denied_endpoint(request)
            self.assertEqual(response.status_code, 503)

    def test_gateway_cors_is_excluded_and_human_preflight_preserved(self):
        import ast
        from pathlib import Path

        tree = ast.parse((Path(__file__).resolve().parents[3] / "townlit_b/settings.py").read_text())
        pattern = next(ast.literal_eval(node.value) for node in tree.body
                       if isinstance(node, ast.Assign)
                       and any(isinstance(target, ast.Name) and target.id == "CORS_URLS_REGEX"
                               for target in node.targets))
        with override_settings(MIDDLEWARE=["corsheaders.middleware.CorsMiddleware"],
                               CORS_ALLOW_ALL_ORIGINS=True, CORS_URLS_REGEX=pattern):
            for path, status in (("/api/v1/ai-integrations/capabilities/", 503),
                                 ("/api/v1/human-synthetic/", 200)):
                response = self.client.options(path, HTTP_ORIGIN="https://synthetic.example.invalid",
                                               HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET")
                self.assertEqual(response.status_code, status)
                self.assertEqual("access-control-allow-origin" in response, status == 200)
