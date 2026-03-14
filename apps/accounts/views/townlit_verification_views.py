# apps/accounts/views/townlit_verification_views.py

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.profiles.models import Member
from apps.accounts.serializers.townlit_verification_serializers import (
    TownlitVerificationEligibilitySerializer,
    TownlitVerificationStatusSerializer,
)
from apps.accounts.services.townlit_engine import (
    get_member_townlit_state,
    evaluate_and_apply_member_townlit_badge,
)


class TownlitVerificationViewSet(viewsets.ViewSet):
    """
    TownLIT gold badge endpoints.

    This layer is separate from provider identity verification.
    It is Member-only and is evaluated automatically.
    """

    def _get_member(self, user):
        return Member.objects.filter(user=user).select_related("user").first()

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def eligibility(self, request):
        member = self._get_member(request.user)

        if not member:
            payload = {
                "is_member": False,
                "identity_verified": bool(getattr(request.user, "is_verified_identity", False)),
                "score": 0,
                "threshold": 0,
                "remaining_score": 0,
                "hard_requirements_ready": False,
                "score_ready": False,
                "eligible_for_initial_gold_unlock": False,
                "already_townlit_verified": False,
                "missing_requirements": ["member_profile"],
            }
            serializer = TownlitVerificationEligibilitySerializer(payload)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # Important:
        # This endpoint can safely auto-apply / auto-revoke because gold is automatic.
        state = evaluate_and_apply_member_townlit_badge(member)

        payload = {
            "is_member": True,
            "identity_verified": state["identity_verified"],
            "score": state["score"],
            "threshold": state["threshold"],
            "remaining_score": state["remaining_score"],
            "hard_requirements_ready": state["hard_requirements_ready"],
            "score_ready": state["score_ready"],
            "eligible_for_initial_gold_unlock": state["eligible_for_initial_gold_unlock"],
            "already_townlit_verified": state["already_townlit_verified"],
            "missing_requirements": state["missing_requirements"],
            "is_townlit_verified": state["is_townlit_verified"],
            "townlit_verified_at": state["townlit_verified_at"],
            "townlit_verified_reason": state["townlit_verified_reason"],
        }

        serializer = TownlitVerificationEligibilitySerializer(payload)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def status(self, request):
        member = self._get_member(request.user)

        if not member:
            payload = {
                "is_member": False,
                "identity_verified": bool(getattr(request.user, "is_verified_identity", False)),
                "is_townlit_verified": False,
                "townlit_verified_at": None,
                "townlit_verified_reason": None,
                "score": 0,
                "threshold": 0,
                "remaining_score": 0,
                "hard_requirements_ready": False,
                "score_ready": False,
                "missing_requirements": ["member_profile"],
            }
            serializer = TownlitVerificationStatusSerializer(payload)
            return Response(serializer.data, status=status.HTTP_200_OK)

        state = get_member_townlit_state(member)

        payload = {
            "is_member": True,
            "identity_verified": state["identity_verified"],
            "is_townlit_verified": bool(member.is_townlit_verified),
            "townlit_verified_at": member.townlit_verified_at,
            "townlit_verified_reason": member.townlit_verified_reason,
            "score": state["score"],
            "threshold": state["threshold"],
            "remaining_score": state["remaining_score"],
            "hard_requirements_ready": state["hard_requirements_ready"],
            "score_ready": state["score_ready"],
            "missing_requirements": state["missing_requirements"],
        }

        serializer = TownlitVerificationStatusSerializer(payload)
        return Response(serializer.data, status=status.HTTP_200_OK)