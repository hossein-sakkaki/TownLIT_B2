# townlit_b/security_logging.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-22.
# Last Update by Hossein Sakkaki on 2026-10-22.

import logging
import re


_TOKEN_PATTERN = re.compile(
    r"(?i)(\b(?:access_token|refresh_token|id_token|token|jwt|authorization)=)"
    r"([^\s&;#\"'<>]+)"
)

_BEARER_PATTERN = re.compile(
    r"(?i)(\bBearer\s+)[A-Za-z0-9._~+/=-]+"
)


def redact_sensitive_text(value: str) -> str:
    value = _TOKEN_PATTERN.sub(
        lambda match: f"{match.group(1)}[REDACTED]",
        value,
    )
    return _BEARER_PATTERN.sub(
        lambda match: f"{match.group(1)}[REDACTED]",
        value,
    )


def _redact_argument(value):
    if isinstance(value, str):
        return redact_sensitive_text(value)

    if isinstance(value, tuple):
        return tuple(_redact_argument(item) for item in value)

    if isinstance(value, list):
        return [_redact_argument(item) for item in value]

    if isinstance(value, dict):
        return {
            key: _redact_argument(item)
            for key, item in value.items()
        }

    return value


class SensitiveTokenLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_sensitive_text(record.msg)

        if record.args:
            record.args = _redact_argument(record.args)

        return True


def install_sensitive_logging_filters() -> None:
    logger_names = (
        "uvicorn.error",
        "uvicorn.access",
        "gunicorn.error",
        "gunicorn.access",
    )

    for logger_name in logger_names:
        logger = logging.getLogger(logger_name)

        if not any(
            isinstance(item, SensitiveTokenLogFilter)
            for item in logger.filters
        ):
            logger.addFilter(SensitiveTokenLogFilter())
