# apps/ai_gateway/views.py
# TownLIT-Backend
# Created by Codex on 2026-11-06.
# Last Update by Codex on 2026-11-06.

from uuid import uuid4

from django.conf import settings

from .audit import log_denial
from .errors import GatewayDenied, error_response
from .security import UnavailableSecurity


def denied_endpoint(request, **kwargs):
    """B1 exposes denial stubs only, including token and capabilities paths.

    Retain normal Django middleware/CSRF protections. Do not inspect request.user,
    certificates, JSON or Authorization here, and never return capabilities yet.
    """
    request_id = uuid4()
    code = "gateway_disabled"
    if getattr(settings, "AI_GATEWAY_ENABLED", False) is True:
        try:
            UnavailableSecurity().verify(request)
        except GatewayDenied as exc:
            code = exc.code
        except Exception:
            code = "security_unavailable"
    try:
        log_denial(request_id, code)
    except Exception:
        code = "security_unavailable"
    return error_response(code, request_id)
