# apps/core/exceptions.py
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.response import Response
from rest_framework import status

def custom_exception_handler(exc, context):
    """
    Thin wrapper around DRF's default handler:
    - Uses default mapping
    - Normalizes payload to {"message": "...", "error": ...}
    """
    resp = drf_exception_handler(exc, context)
    if resp is None:
        # Not handled by DRF default (e.g., plain Exception)
        return Response(
            {"message": "An unexpected error occurred.", "error": str(exc)},
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
