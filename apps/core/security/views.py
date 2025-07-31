from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import CustomUser
from utils.security.destructive_actions import handle_destructive_pin_actions
from .access import grant_litshield_access, check_litshield_access, revoke_litshield_access


class LITShieldAccessViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    # Enter ------------------------------------------------------------
    @action(detail=False, methods=["post"])
    def enter(self, request):
        scope = request.data.get("scope")
        pin = request.data.get("pin")

        if not scope:
            return Response({"error": "Scope is required."}, status=status.HTTP_400_BAD_REQUEST)

        user: CustomUser = request.user

        if not getattr(user, "pin_security_enabled", False):
            return grant_litshield_access(scope, user)

        if not pin:
            return Response({"error": "PIN is required."}, status=status.HTTP_400_BAD_REQUEST)        
        
        if user.verify_access_pin(pin) or user.verify_delete_pin(pin):
            if user.verify_delete_pin(pin):
                try:
                    handle_destructive_pin_actions(user)
                except ImportError:
                    pass

            return grant_litshield_access(scope, user)
        return Response({"error": "Wrong PIN!"}, status=status.HTTP_403_FORBIDDEN)

    # Check ------------------------------------------------------------
    @action(detail=False, methods=["get"])
    def check(self, request):
        scope = request.query_params.get("scope")
        if not scope:
            return Response({"error": "Scope is required."}, status=status.HTTP_400_BAD_REQUEST)

        return check_litshield_access(scope, request)

    # Logout ------------------------------------------------------------
    @action(detail=False, methods=["post"])
    def logout(self, request):
        scopes = request.data.get("scopes")
        single_scope = request.data.get("scope")

        if scopes and isinstance(scopes, list):
            response = Response({"message": "All scopes revoked."}, status=200)
            for scope in scopes:
                response.delete_cookie(
                    f"{scope}_access",
                    path="/",
                    samesite="Lax",
                )
                
            return response

        if single_scope:
            return revoke_litshield_access(single_scope)

        return Response({"error": "At least one scope is required."}, status=status.HTTP_400_BAD_REQUEST)