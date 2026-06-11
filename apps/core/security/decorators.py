
# apps/core/security/decorators.py

from functools import wraps

from rest_framework import status
from rest_framework.response import Response

from apps.core.security.access import (
    has_litshield_access,
    normalize_litshield_scope,
)


def require_litshield_access(scope: str = "general"):
    """
    Protect DRF actions with LITShield.

    Web:
    - accepts secure HttpOnly cookie.

    Mobile:
    - accepts server-side user/scope/device grant,
      but only when X-Device-ID belongs to the authenticated user.
    """
    normalized_scope = normalize_litshield_scope(scope)

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(self, request, *args, **kwargs):
            user = request.user

            if not user or not user.is_authenticated:
                return Response(
                    {"error": "Authentication required."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            if not normalized_scope:
                return Response(
                    {"error": "Invalid LITShield scope."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if has_litshield_access(normalized_scope, request):
                return view_func(self, request, *args, **kwargs)

            return Response(
                {
                    "error": f"LITShield PIN access required for {normalized_scope}.",
                    "code": "LITSHIELD_ACCESS_REQUIRED",
                    "scope": normalized_scope,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        return _wrapped_view

    return decorator

