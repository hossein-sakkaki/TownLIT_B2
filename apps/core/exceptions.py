# apps/core/exceptions.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-19.
# Last Update by Hossein Sakkaki on 2026-10-19.

import logging

from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.response import Response
from rest_framework import status


logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Thin wrapper around DRF's default handler:
    - Uses default mapping
    - Normalizes payload to {"message": "...", "error": ...}
    """
    resp = drf_exception_handler(exc, context)
    if resp is None:
        # Request paths may contain password-reset bearer tokens. Exception
        # messages and tracebacks can also include tokens or credentials.
        # Never write those untrusted values to the general application log.
        request = context.get("request")
        view = context.get("view")
        method = getattr(request, "method", "UNKNOWN")
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
            method = "UNKNOWN"
        view_name = type(view).__name__ if view is not None else "UNKNOWN"
        logger.error(
            "Unhandled API exception: method=%s view=%s exception_type=%s",
            method,
            view_name,
            type(exc).__name__,
        )
        return Response(
            {"message": "An unexpected error occurred.", "error": "Internal server error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    data = resp.data
    # Normalize common shapes
    message = None
    if isinstance(data, dict):
        message = data.get("detail") or data.get("message")
    elif isinstance(data, list) and data:
        message = data[0]

    normalized = {
        "message": message or "Request failed.",
        "error": data,
    }
    return Response(normalized, status=resp.status_code)
