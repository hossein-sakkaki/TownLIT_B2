# apps/core/security/account_gate/middleware.py

from __future__ import annotations

from django.http import JsonResponse

from apps.core.security.account_gate.constants import (
    API_PREFIX,
    RESTRICTED_OWNER_ALLOWED_EXACT_PATHS,
    RESTRICTED_OWNER_ALLOWED_PREFIXES,
    RESTRICTED_OWNER_CODE,
    RESTRICTED_OWNER_DETAIL,
    RESTRICTED_OWNER_PROFILE_GATE,
)
from apps.core.security.account_gate.service import (
    is_restricted_owner_user,
    resolve_authenticated_user_from_request,
)


class RestrictedOwnerAccountGateMiddleware:
    """
    Central app-wide API gate for owner accounts whose profile is temporarily
    unavailable.

    This middleware is separate from LITShield.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._should_skip_request(request):
            return self.get_response(request)

        user = resolve_authenticated_user_from_request(request)

        if not user:
            return self.get_response(request)

        if not is_restricted_owner_user(user):
            return self.get_response(request)

        if self._is_allowed_restricted_path(request, user):
            return self.get_response(request)

        return self._restricted_response()

    def _should_skip_request(self, request) -> bool:
        if request.method == "OPTIONS":
            return True

        path = request.path_info or ""

        if not path.startswith(API_PREFIX):
            return True

        return False

    def _is_allowed_restricted_path(self, request, user) -> bool:
        path = self._normalize_path(request.path_info or "")

        if path in RESTRICTED_OWNER_ALLOWED_EXACT_PATHS:
            return True

        if any(path.startswith(prefix) for prefix in RESTRICTED_OWNER_ALLOWED_PREFIXES):
            return True

        if self._is_self_avatar_asset_request(request, user):
            return True

        return False

    def _is_self_avatar_asset_request(self, request, user) -> bool:
        """
        Allow only the restricted owner's own avatar image.

        This keeps limited profile UI usable without opening general
        asset access.
        """
        path = self._normalize_path(request.path_info or "")

        if path != "/api/v1/assets/playback/image/":
            return False

        app_label = str(request.GET.get("app_label", "")).lower()
        model = str(request.GET.get("model", "")).lower()
        object_id = str(request.GET.get("object_id", ""))
        field_name = str(request.GET.get("field_name", "")).lower()

        return (
            app_label == "accounts"
            and model == "customuser"
            and object_id == str(user.id)
            and field_name == "image_name"
        )

    def _normalize_path(self, path: str) -> str:
        if not path.startswith("/"):
            path = f"/{path}"

        if not path.endswith("/"):
            path = f"{path}/"

        return path

    def _restricted_response(self):
        response = JsonResponse(
            {
                "code": RESTRICTED_OWNER_CODE,
                "detail": RESTRICTED_OWNER_DETAIL,
                "profile_gate": RESTRICTED_OWNER_PROFILE_GATE,
            },
            status=403,
        )

        response["X-TownLIT-Gate"] = RESTRICTED_OWNER_CODE
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response["Pragma"] = "no-cache"

        return response