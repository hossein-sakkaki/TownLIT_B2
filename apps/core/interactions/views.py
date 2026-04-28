# apps/core/interactions/views.py
from django.apps import apps
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


def _resolve_content_type(raw_value):
    """
    Accepts:
      - numeric id: "23"
      - dotted key: "posts.testimony"
      - plain model: "testimony"
    Returns:
      - ContentType instance
    Raises:
      - ContentType.DoesNotExist
    """
    raw = str(raw_value).strip()

    if raw.isdigit():
        return ContentType.objects.get(pk=int(raw))

    if "." in raw:
        app_label, model = raw.split(".", 1)
        return ContentType.objects.get(app_label=app_label, model=model)

    return ContentType.objects.get(model=raw)


def _resolve_model_class(ct: ContentType):
    """
    Resolve a stable model class even if ct.model_class() is None.
    Supports stale/legacy content-type aliases like posts.pray -> posts.Prayer.
    """
    model_class = ct.model_class()
    if model_class is not None:
        return model_class

    # 1) direct fallback
    try:
        model_class = apps.get_model(ct.app_label, ct.model)
        if model_class is not None:
            return model_class
    except Exception:
        pass

    # 2) known legacy aliases
    alias_map = {
        ("posts", "pray"): "Prayer",
    }

    alias_target = alias_map.get((ct.app_label, ct.model))
    if alias_target:
        try:
            model_class = apps.get_model(ct.app_label, alias_target)
            if model_class is not None:
                return model_class
        except Exception:
            pass

    return None


def _fetch_target_reaction_counters(model_class, object_id):
    """
    Read denormalized counters without hydrating the model instance.
    This avoids recursion caused by problematic model properties /
    custom attribute resolution / deep model graph side effects.
    """
    return (
        model_class.objects
        .filter(pk=object_id)
        .values("reactions_count", "reactions_breakdown")
        .first()
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
    # 🔍 Reaction summary
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

        try:
            object_id = int(object_id)
        except (TypeError, ValueError):
            return Response(
                {"detail": "Invalid object_id."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            ct = _resolve_content_type(content_type_param)
        except ContentType.DoesNotExist:
            return Response(
                {"detail": "Invalid content_type."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        model_class = _resolve_model_class(ct)
        if not model_class:
            return Response(
                {
                    "detail": (
                        f"Invalid target model. "
                        f"content_type={ct.app_label}.{ct.model}"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        target = _fetch_target_reaction_counters(model_class, object_id)
        if not target:
            return Response(
                {"detail": "Target not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

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
            "content_type": content_type_param,
            "object_id": object_id,
            "reactions_count": target.get("reactions_count") or 0,
            "reactions_breakdown": target.get("reactions_breakdown") or {},
            "my_reaction": my_reaction,
        }

        return Response(
            ReactionSummarySerializer(payload).data,
            status=status.HTTP_200_OK,
        )

    # ------------------------------------------------------------------
    # 🔁 Reaction toggle
    # ------------------------------------------------------------------
    @action(detail=False, methods=["post"])
    @transaction.atomic
    def toggle(self, request):
        serializer = ReactionToggleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        content_type_param = serializer.validated_data["content_type"]
        object_id = serializer.validated_data["object_id"]
        reaction_type = serializer.validated_data["reaction_type"]

        try:
            ct = _resolve_content_type(content_type_param)
        except ContentType.DoesNotExist:
            return Response(
                {"detail": "Invalid content_type."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        model_class = _resolve_model_class(ct)
        if not model_class:
            return Response(
                {
                    "detail": (
                        f"Invalid target model. "
                        f"content_type={ct.app_label}.{ct.model}"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        target = _fetch_target_reaction_counters(model_class, object_id)
        if not target:
            return Response(
                {"detail": "Target not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        user = request.user

        existing = (
            Reaction.objects
            .select_for_update()
            .filter(
                content_type=ct,
                object_id=object_id,
                name=user,
            )
        )

        if existing.exists():
            current = existing.first()

            if current.reaction_type == reaction_type:
                current.delete()
                action_name = "removed"
            else:
                current.delete()
                Reaction.objects.create(
                    content_type=ct,
                    object_id=object_id,
                    name=user,
                    reaction_type=reaction_type,
                )
                action_name = "changed"
        else:
            Reaction.objects.create(
                content_type=ct,
                object_id=object_id,
                name=user,
                reaction_type=reaction_type,
            )
            action_name = "added"

        target = _fetch_target_reaction_counters(model_class, object_id)
        if not target:
            return Response(
                {"detail": "Target not found after toggle."},
                status=status.HTTP_404_NOT_FOUND,
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
            "content_type": content_type_param,
            "object_id": object_id,
            "action": action_name,
            "reactions_count": target.get("reactions_count") or 0,
            "reactions_breakdown": target.get("reactions_breakdown") or {},
            "my_reaction": my_reaction,
        }

        return Response(
            ReactionSummarySerializer(payload).data,
            status=status.HTTP_200_OK,
        )