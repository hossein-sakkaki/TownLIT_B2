# utils/api/error_response.py

from rest_framework import status
from rest_framework.response import Response


def _first_error_message(errors):
    """
    Extract first readable message from DRF nested errors.
    """
    if isinstance(errors, list):
        if not errors:
            return None

        first = errors[0]
        return str(first)

    if isinstance(errors, dict):
        for value in errors.values():
            message = _first_error_message(value)
            if message:
                return message

    if errors:
        return str(errors)

    return None


def build_validation_error_response(
    serializer_errors,
    fallback="Invalid data. Please check the provided fields.",
):
    """
    Return a client-friendly validation error response.
    Keeps details for field mapping and exposes first message as top-level error.
    """
    message = _first_error_message(serializer_errors) or fallback

    return Response(
        {
            "error": message,
            "message": message,
            "details": serializer_errors,
        },
        status=status.HTTP_400_BAD_REQUEST,
    )