# apps/ai_gateway/audit.py
# TownLIT-Backend
# Created by Codex on 2026-11-06.
# Last Update by Codex on 2026-11-06.

"""Bounded denial events; no caller identity, URL, body or credential logging."""

import logging

from .errors import ERRORS


logger = logging.getLogger("townlit.ai_gateway")


def log_denial(request_id, code):
    safe_code = code if code in ERRORS else "access_denied"
    logger.info("gateway_denied request_id=%s code=%s", request_id, safe_code)
