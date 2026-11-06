# apps/accounts/tests/test_backend_exception_redaction.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-05.
# Last Update by Hossein Sakkaki on 2026-11-05.
#

from types import SimpleNamespace
from unittest.mock import patch

from django.db import OperationalError
from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from apps.core.exceptions import custom_exception_handler


class BackendExceptionRedactionTests(SimpleTestCase):
    def test_unhandled_error_does_not_log_or_return_reset_token(self):
        token = "r2_SENSITIVE_TEST_TOKEN"
        request = SimpleNamespace(
            method="POST",
            path=f"/api/v1/accounts/auth/reset-password/{token}/",
        )
        error = OperationalError(f"Database error while handling {token}")
        with patch("apps.core.exceptions.logger.error") as log_error:
            response = custom_exception_handler(
                error, {"request": request, "view": SimpleNamespace()},
            )

        self.assertEqual(response.status_code, 500)
        log_error.assert_called_once()
        self.assertNotIn(token, str(log_error.call_args))
        self.assertNotIn(token, str(response.data))
        self.assertNotIn("Database error", str(response.data))
        self.assertEqual(response.data["error"], "Internal server error.")

    def test_expected_validation_errors_still_use_existing_contract(self):
        response = custom_exception_handler(
            ValidationError({"new_password": ["Invalid password."]}),
            {"request": SimpleNamespace(method="POST"), "view": SimpleNamespace()},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("message", response.data)
        self.assertIn("error", response.data)
        self.assertIn("new_password", response.data["error"])
