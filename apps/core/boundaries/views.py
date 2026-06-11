# apps/core/boundaries/views.py

from django.contrib.auth import get_user_model
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.boundaries.constants import (
    BOUNDARY_STILLNESS,
    BOUNDARY_BOUNDARY,
    BOUNDARY_GENERIC_UNAVAILABLE_MESSAGE,
)
from apps.core.boundaries.models import UserBoundary
from apps.core.boundaries.serializers import (
    UserBoundarySerializer,
    BoundarySetSerializer,
    BoundaryRemoveSerializer,
)
from apps.core.boundaries.services.actions import BoundaryActionService
from apps.core.boundaries.services.policy import BoundaryPolicy
from apps.core.boundaries.serializers import boundary_unavailable_reason_to_text

CustomUser = get_user_model()


class UserBoundaryViewSet(viewsets.GenericViewSet):
    """
    Peace & Boundaries API.

    UI naming:
    - Stillness: quiet distance
    - Boundary: protective interaction pause

    Sanctuary remains a separate reporting/review system.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = UserBoundarySerializer

    def get_queryset(self):
        return (
            UserBoundary.objects
            .select_related(
                "owner",
                "target",
                "owner__label",
                "target__label",
            )
            .filter(owner=self.request.user, is_active=True)
            .order_by("-created_at")
        )

    def list(self, request):
        qs = self.get_queryset()
        boundary_type = request.query_params.get("type")

        if boundary_type in {BOUNDARY_STILLNESS, BOUNDARY_BOUNDARY}:
            qs = qs.filter(boundary_type=boundary_type)

        serializer = self.get_serializer(
            qs,
            many=True,
            context={"request": request},
        )

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="set")
    def set_boundary(self, request):
        serializer = BoundarySetSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        obj, cleanup = BoundaryActionService.set_boundary(
            owner=request.user,
            target=serializer.validated_data["target"],
            boundary_type=serializer.validated_data["boundary_type"],
            source=serializer.validated_data.get("source") or "",
            reason=serializer.validated_data.get("reason") or "",
            note=serializer.validated_data.get("note") or "",
        )

        output = UserBoundarySerializer(
            obj,
            context={"request": request},
        ).data

        return Response(
            {
                "message": "Peace setting updated.",
                "data": output,
                "cleanup": {
                    "relationships_cleaned": cleanup.cleaned_any,
                    "friendships_cleaned": cleanup.friendships_cleaned,
                    "fellowships_cleaned": cleanup.fellowships_cleaned,
                },
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="remove")
    def remove_boundary(self, request):
        serializer = BoundaryRemoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        removed = BoundaryActionService.remove_boundary(
            owner=request.user,
            target=serializer.validated_data["target"],
            boundary_type=serializer.validated_data["boundary_type"],
        )

        return Response(
            {
                "message": "Peace setting removed." if removed else "No active peace setting found.",
                "removed": removed,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="state")
    def state(self, request):
        raw_target_id = request.query_params.get("target_user_id")

        if not raw_target_id:
            return Response(
                {"error": "target_user_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            target_id = int(raw_target_id)
        except Exception:
            return Response(
                {"error": "Invalid target_user_id."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target = CustomUser.objects.filter(id=target_id).first()

        if not target:
            return Response(
                {"error": "Target user not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        in_stillness = BoundaryPolicy.is_in_stillness(
            owner=request.user,
            target=target,
        )

        has_boundary = BoundaryPolicy.has_boundary(
            owner=request.user,
            target=target,
        )

        has_boundary_between = BoundaryPolicy.has_boundary_between(
            request.user,
            target,
        )

        reason = None

        if has_boundary_between:
            reason = boundary_unavailable_reason_to_text(
                BOUNDARY_GENERIC_UNAVAILABLE_MESSAGE
            )

        return Response(
            {
                "target_user_id": target.id,
                "in_stillness": in_stillness,
                "has_boundary": has_boundary,
                "has_boundary_between": has_boundary_between,
                "direct_interaction_available": not has_boundary_between,
                "direct_interaction_unavailable_reason": reason,
            },
            status=status.HTTP_200_OK,
        )