# apps/ai_gateway/errors.py
# TownLIT-Backend
# Created by Codex on 2026-11-06.
# Last Update by Codex on 2026-11-06.

from types import MappingProxyType
from uuid import uuid4

from django.http import JsonResponse


ERRORS = MappingProxyType({
    "gateway_disabled": (503, "Gateway is disabled.", False),
    "security_unavailable": (503, "Gateway security is unavailable.", False),
    "access_denied": (403, "Gateway access denied.", False),
    "invalid_request": (400, "Invalid Gateway request.", False),
    "nonce_reused": (409, "Request proof was already used.", False),
    "idempotency_conflict": (409, "Idempotency key conflict.", False),
})


class GatewayDenied(Exception):
    def __init__(self, code="access_denied"):
        self.code = code if code in ERRORS else "access_denied"
        super().__init__(self.code)


def error_response(code, request_id):
    status, message, retryable = ERRORS[code]
    response = JsonResponse({
        "error": {"code": code, "message": message,
                  "retryable": retryable, "field_errors": []},
        # Unverified correlation headers never become trusted context.
        "correlation_id": str(uuid4()),
        "request_id": str(request_id),
    }, status=status)
    response["Cache-Control"] = "no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
