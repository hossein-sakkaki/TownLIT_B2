# tests/test_security_logging.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-22.
# Last Update by Hossein Sakkaki on 2026-10-22.

import logging
import unittest

# Load the standalone logging module without Django initialization.
import importlib.util
from pathlib import Path

module_path = (
    Path(__file__).resolve().parents[1]
    / "townlit_b"
    / "security_logging.py"
)

spec = importlib.util.spec_from_file_location(
    "townlit_security_logging_test",
    module_path,
)

assert spec is not None and spec.loader is not None

security_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(security_module)

SensitiveTokenLogFilter = security_module.SensitiveTokenLogFilter
install_sensitive_logging_filters = (
    security_module.install_sensitive_logging_filters
)
redact_sensitive_text = security_module.redact_sensitive_text


class SensitiveLoggingTests(unittest.TestCase):

    def test_websocket_token_redaction(self):
        message = (
            "/ws/notifications/?token=sample.jwt.value"
            "&device=ios"
        )
        result = redact_sensitive_text(message)

        self.assertNotIn("sample.jwt.value", result)
        self.assertIn("token=[REDACTED]", result)
        self.assertIn("device=ios", result)

    def test_multiple_sensitive_parameters(self):
        message = (
            "/ws/?token=abc&refresh_token=xyz"
        )
        result = redact_sensitive_text(message)

        self.assertNotIn("token=abc", result)
        self.assertNotIn("refresh_token=xyz", result)

    def test_uvicorn_websocket_record(self):
        record = logging.LogRecord(
            "uvicorn.error",
            logging.INFO,
            __file__,
            1,
            '%s - "WebSocket %s" [accepted]',
            (
                "127.0.0.1:12345",
                "/ws/?token=sample.jwt.value",
            ),
            None,
        )

        SensitiveTokenLogFilter().filter(record)

        rendered = record.getMessage()

        self.assertNotIn("sample.jwt.value", rendered)
        self.assertIn("token=[REDACTED]", rendered)

    def test_uvicorn_access_formatter(self):
        from uvicorn.logging import AccessFormatter

        record = logging.LogRecord(
            "uvicorn.access",
            logging.INFO,
            __file__,
            1,
            '%s - "%s %s HTTP/%s" %d',
            (
                "127.0.0.1:12345",
                "GET",
                "/ws/?token=sample.jwt.value",
                "1.1",
                101,
            ),
            None,
        )

        SensitiveTokenLogFilter().filter(record)
        rendered = AccessFormatter().format(record)

        self.assertNotIn("sample.jwt.value", rendered)
        self.assertIn("token=[REDACTED]", rendered)

    def test_installation_is_idempotent(self):
        install_sensitive_logging_filters()
        install_sensitive_logging_filters()

        logger = logging.getLogger("uvicorn.error")
        count = sum(
            isinstance(item, SensitiveTokenLogFilter)
            for item in logger.filters
        )

        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
