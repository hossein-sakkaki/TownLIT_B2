# apps/core/interactions/views.py
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.posts.models.reaction import Reaction
from apps.core.interactions.serializers import (
    ReactionSummarySerializer,
    ReactionToggleSerializer,
)


class InteractionReactionViewSet(viewsets.ModelViewSet):
    """
    Unified Reaction interaction endpoints.

    This ViewSet is NOT the legacy Reaction CRUD.
    It is a lightweight interaction layer used by UI.

    Endpoints:
    - GET    /interactions/reactions/summary/
    - POST   /interactions/reactions/toggle/
    """

    permission_classes = [permissions.IsAuthenticated]
    queryset = Reaction.objects.none()  # not used (action-based only)

    # ------------------------------------------------------------------
    # 🔍 Reaction summary (hover / modal / sync)
    # ------------------------------------------------------------------
    @action(detail=False, methods=["get"])
    def summary(self, request):
        content_type_param = request.query_params.get("content_type")
        object_id = request.query_params.get("object_id")

        if not content_type_param or not object_id:
            return Response(
                {"detail": "content_type and object_id are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Resolve ContentType
        try:
            ct = ContentType.objects.get(model=content_type_param)
        except ContentType.DoesNotExist:
            return Response(
                {"detail": "Invalid content_type."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        model_class = ct.model_class()
        if not model_class:
            return Response(
                {"detail": "Invalid target model."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Fetch target (DENORMALIZED FIELDS ONLY)
        try:
            target = (
                model_class.objects
                .only("reactions_count", "reactions_breakdown")
                .get(pk=object_id)
            )
        except model_class.DoesNotExist:
            return Response(
                {"detail": "Target not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Current user's reaction (optional)
        my_reaction = (
            Reaction.objects
            .filter(
                content_type=ct,
                object_id=object_id,
                name=request.user,
            )
            .values_list("reaction_type", flat=True)
            .first()
        )

        payload = {
            "reactions_count": target.reactions_count,
            "reactions_breakdown": target.reactions_breakdown or {},
            "my_reaction": my_reaction,
        }

        return Response(
            ReactionSummarySerializer(payload).data,
            status=status.HTTP_200_OK,
        )

    # ------------------------------------------------------------------
    # 🔁 Reaction toggle (idempotent, race-safe)
    # ------------------------------------------------------------------
    @action(detail=False, methods=["post"])
    @transaction.atomic
    def toggle(self, request):
        serializer = ReactionToggleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        content_type_param = serializer.validated_data["content_type"]
        object_id = serializer.validated_data["object_id"]
        reaction_type = serializer.validated_data["reaction_type"]

        # Resolve ContentType
        try:
            ct = ContentType.objects.get(model=content_type_param)
        except ContentType.DoesNotExist:
            return Response(
                {"detail": "Invalid content_type."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user

        # Lock existing reactions for this user + target
        existing = (
            Reaction.objects
            .select_for_update()
            .filter(
                content_type=ct,
                object_id=object_id,
                name=user,
            )
        )

        # Toggle logic
        if existing.exists():
            current = existing.first()

            if current.reaction_type == reaction_type:
                current.delete()
                action = "removed"
            else:
                current.delete()
                Reaction.objects.create(
                    content_type=ct,
                    object_id=object_id,
                    name=user,
                    reaction_type=reaction_type,
                )
                action = "changed"
        else:
            Reaction.objects.create(
                content_type=ct,
                object_id=object_id,
                name=user,
                reaction_type=reaction_type,
            )
            action = "added"

        # Fetch updated summary (single source of truth)
        model_class = ct.model_class()
        target = (
            model_class.objects
            .only("reactions_count", "reactions_breakdown")
            .get(pk=object_id)
        )

        my_reaction = (
            Reaction.objects
            .filter(
                content_type=ct,
                object_id=object_id,
                name=user,
            )
            .values_list("reaction_type", flat=True)
            .first()
        )

        payload = {
            "action": action,
            "reactions_count": target.reactions_count,
            "reactions_breakdown": target.reactions_breakdown or {},
            "my_reaction": my_reaction,
        }

        return Response(
            ReactionSummarySerializer(payload).data,
            status=status.HTTP_200_OK,
        )
