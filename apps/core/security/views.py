# apps/core/security/views.py

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models.user import CustomUser
from utils.security.security_manager import SecurityStateManager
from utils.security.destructive_actions import handle_destructive_pin_actions

from .access import (
    check_litshield_access,
    clear_litshield_pin_failures,
    get_litshield_pin_lock_status,
    get_request_device_id,
    grant_litshield_access,
    is_registered_active_device,
    normalize_litshield_scope,
    record_litshield_pin_failure,
    revoke_litshield_access,
)


class LITShieldAccessViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    # -----------------------------------------------------------------
    # Enter
    # -----------------------------------------------------------------
    @action(detail=False, methods=["post"])
    def enter(self, request):
        raw_scope = request.data.get("scope")
        scope = normalize_litshield_scope(raw_scope)
        pin = request.data.get("pin")

        if not scope:
            return Response(
                {
                    "error": "Valid scope is required.",
                    "code": "INVALID_SCOPE",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user: CustomUser = request.user
        device_id = get_request_device_id(request)

        # If device id is provided, it must be a registered active device.
        # This protects mobile/device-bound access from forged random device ids.
        if device_id and not is_registered_active_device(user, device_id):
            return Response(
                {
                    "error": "Registered device is required for LITShield access.",
                    "code": "UNREGISTERED_DEVICE",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # If PIN security is off, grant access without PIN.
        if not getattr(user, "pin_security_enabled", False):
            return grant_litshield_access(
                scope,
                user,
                request=request,
            )

        # Check temporary lock before validating PIN.
        lock_status = get_litshield_pin_lock_status(
            request=request,
            user=user,
            scope=scope,
        )

        if lock_status.get("locked"):
            return Response(
                {
                    "error": "Too many incorrect PIN attempts. Please try again later.",
                    "code": "LITSHIELD_PIN_LOCKED",
                    "locked_until": lock_status.get("locked_until"),
                    "remaining_seconds": lock_status.get("remaining_seconds"),
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        if not pin:
            return Response(
                {
                    "error": "PIN is required.",
                    "code": "PIN_REQUIRED",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        pin = str(pin).strip()

        # Normal access PIN
        if user.verify_access_pin(pin):
            clear_litshield_pin_failures(
                request=request,
                user=user,
                scope=scope,
            )

            SecurityStateManager.unhide_confidants(user)

            return grant_litshield_access(
                scope,
                user,
                request=request,
            )

        # Destructive PIN
        if user.verify_delete_pin(pin):
            clear_litshield_pin_failures(
                request=request,
                user=user,
                scope=scope,
            )

            try:
                handle_destructive_pin_actions(user)
            except ImportError:
                pass

            return grant_litshield_access(
                scope,
                user,
                request=request,
                response_data={
                    "destructive_action_triggered": True,
                },
            )

        # Wrong PIN
        failure = record_litshield_pin_failure(
            request=request,
            user=user,
            scope=scope,
        )

        if failure.get("locked"):
            return Response(
                {
                    "error": "Too many incorrect PIN attempts. Please try again later.",
                    "code": "LITSHIELD_PIN_LOCKED",
                    "locked_until": failure.get("locked_until"),
                    "remaining_seconds": failure.get("remaining_seconds"),
                    "attempts_remaining": 0,
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        return Response(
            {
                "error": "Wrong PIN.",
                "code": "WRONG_PIN",
                "attempts_remaining": failure.get("attempts_remaining"),
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    # -----------------------------------------------------------------
    # Check
    # -----------------------------------------------------------------
    @action(detail=False, methods=["get"])
    def check(self, request):
        raw_scope = request.query_params.get("scope")
        scope = normalize_litshield_scope(raw_scope)

        if not scope:
            return Response(
                {
                    "error": "Valid scope is required.",
                    "code": "INVALID_SCOPE",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return check_litshield_access(scope, request)

    # -----------------------------------------------------------------
    # Logout
    # -----------------------------------------------------------------
    @action(detail=False, methods=["post"])
    def logout(self, request):
        scopes = request.data.get("scopes")
        single_scope = request.data.get("scope")

        if scopes and isinstance(scopes, list):
            response = Response(
                {"message": "All scopes revoked."},
                status=status.HTTP_200_OK,
            )

            for raw_scope in scopes:
                scope = normalize_litshield_scope(raw_scope)
                if not scope:
                    continue

                scoped_response = revoke_litshield_access(
                    scope,
                    request=request,
                    user=request.user,
                )

                # Copy cookie deletion from scoped response.
                for key, value in scoped_response.cookies.items():
                    response.cookies[key] = value

            return response

        if single_scope:
            scope = normalize_litshield_scope(single_scope)

            if not scope:
                return Response(
                    {
                        "error": "Valid scope is required.",
                        "code": "INVALID_SCOPE",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return revoke_litshield_access(
                scope,
                request=request,
                user=request.user,
            )

        return Response(
            {
                "error": "At least one scope is required.",
                "code": "SCOPE_REQUIRED",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )