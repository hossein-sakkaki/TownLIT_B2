# apps/posts/views/reactions.py

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import models, transaction
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.accounts.serializers.user_serializers import SimpleCustomUserSerializer
from apps.posts.models.reaction import Reaction
from apps.posts.serializers.reactions import ReactionSerializer
from apps.posts.services.boundary_interactions import (
    check_reaction_create_boundary,
    content_interaction_error_payload,
)

logger = logging.getLogger(__name__)
CustomUser = get_user_model()


# -----------------------------------------------------------------------------
# Realtime helpers
# -----------------------------------------------------------------------------
def reaction_target_group_name(ct_id: int, obj_id: int) -> str:
    return f"reactions.target.{ct_id}.{obj_id}"


def reaction_inbox_group_name(ct_id: int, obj_id: int, user_id: int) -> str:
    return f"reactions.inbox.{ct_id}.{obj_id}.{user_id}"


def _safe_reaction_broadcast(group_name: str, event_name: str, payload: dict):
    """
    Send a reaction event without breaking the HTTP flow.
    """
    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            logger.warning("Channel layer not configured; skip reaction WS send.")
            return

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "dispatch_event",
                "app": "reactions",
                "event": event_name,
                "data": payload,
            },
        )
    except Exception:
        logger.exception("Reaction WS broadcast failed (ignored)")


def _reaction_has_message(reaction: Reaction) -> bool:
    """
    Check the decrypted message safely in Python.
    """
    message = getattr(reaction, "message", None)
    return isinstance(message, str) and bool(message.strip())


def _queryset_has_message(queryset) -> bool:
    """
    Check for a non-blank encrypted message without content lookups.
    """
    candidates = queryset.exclude(message__isnull=True).only("id", "message")
    return any(_reaction_has_message(reaction) for reaction in candidates)


def _resolve_owner_user_id(obj, request_user_id=None):
    """
    Resolve the target owner's user ID.
    """
    base = obj

    # Drill into wrapped content when available.
    if hasattr(base, "content_object") and getattr(base, "content_object") is not None:
        base = base.content_object

    # Check common direct owner fields.
    for fk in ("user_id", "name_id", "owner_id", "member_user_id", "org_owner_user_id"):
        if hasattr(base, fk):
            value = getattr(base, fk)
            if isinstance(value, int):
                return value

    # Support Member user ownership.
    if base.__class__.__name__.lower() == "member" and hasattr(base, "user_id"):
        return getattr(base, "user_id", None)

    # Check common related owner objects.
    for relation in ("name", "owner", "member_user", "org_owner_user"):
        if hasattr(base, relation):
            related_obj = getattr(base, relation)
            if getattr(related_obj, "id", None):
                return related_obj.id

    # Support organization owner membership.
    if hasattr(base, "org_owners") and request_user_id:
        try:
            if base.org_owners.filter(id=request_user_id).exists():
                return request_user_id
        except Exception:
            pass

    return None


def _get_target_owner_user_id(cto: ContentType, obj_id, request_user_id=None):
    model_cls = cto.model_class()
    if model_cls is None:
        return None

    try:
        target_obj = model_cls._default_manager.get(pk=obj_id)
    except model_cls.DoesNotExist:
        return None

    return _resolve_owner_user_id(
        target_obj,
        request_user_id=request_user_id,
    )


def _build_summary_payload(cto: ContentType, obj_id, request_user=None):
    """
    Build a fresh reaction summary for realtime sync.
    """
    qs = Reaction.objects.filter(
        content_type=cto,
        object_id=obj_id,
    )

    breakdown_rows = (
        qs.values("reaction_type")
        .annotate(count=models.Count("id"))
        .order_by()
    )

    summary = {
        "content_type_id": cto.id,
        "content_type": f"{cto.app_label}.{cto.model}",
        "object_id": int(obj_id),
        "reactions_count": qs.count(),
        "reactions_breakdown": {
            row["reaction_type"]: row["count"]
            for row in breakdown_rows
        },
        "my_reaction": None,
    }

    if request_user and getattr(request_user, "is_authenticated", False):
        summary["my_reaction"] = (
            qs.filter(name=request_user)
            .values_list("reaction_type", flat=True)
            .first()
        )

    return summary


def _broadcast_target_summary(cto: ContentType, obj_id, request_user=None):
    payload = _build_summary_payload(
        cto,
        obj_id,
        request_user=request_user,
    )

    _safe_reaction_broadcast(
        reaction_target_group_name(cto.id, int(obj_id)),
        "summary_changed",
        payload,
    )


def _broadcast_owner_inbox_changed(
    *,
    cto: ContentType,
    obj_id,
    owner_user_id: int | None,
    action_name: str,
    reaction: Reaction | None = None,
):
    if not owner_user_id:
        return

    payload = {
        "content_type_id": cto.id,
        "content_type": f"{cto.app_label}.{cto.model}",
        "object_id": int(obj_id),
        "owner_user_id": int(owner_user_id),
        "action": action_name,
    }

    if reaction is not None:
        payload.update(
            {
                "id": reaction.id,
                "reaction_type": reaction.reaction_type,
                "timestamp": (
                    reaction.timestamp.isoformat()
                    if reaction.timestamp
                    else None
                ),
                "has_message": _reaction_has_message(reaction),
                "user": {
                    "id": reaction.name.id,
                    "username": getattr(reaction.name, "username", None),
                },
            }
        )

    _safe_reaction_broadcast(
        reaction_inbox_group_name(
            cto.id,
            int(obj_id),
            int(owner_user_id),
        ),
        "inbox_changed",
        payload,
    )


# -----------------------------------------------------------------------------
# Reaction ViewSet
# -----------------------------------------------------------------------------
class ReactionViewSet(
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    Centralized reactions endpoint.

    POST   /posts/reactions/
    GET    /posts/reactions/
    GET    /posts/reactions/summary/
    DELETE /posts/reactions/<id>/
    """

    queryset = Reaction.objects.all().select_related("name", "content_type")
    serializer_class = ReactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        ct = self.request.query_params.get("content_type")
        oid = self.request.query_params.get("object_id")

        if ct and oid:
            try:
                if str(ct).isdigit():
                    cto = ContentType.objects.get(pk=int(ct))
                elif "." in str(ct):
                    app_label, model = str(ct).split(".", 1)
                    cto = ContentType.objects.get(
                        app_label=app_label,
                        model=model,
                    )
                else:
                    cto = ContentType.objects.get(model=str(ct))
            except ContentType.DoesNotExist:
                return Reaction.objects.none()

            qs = qs.filter(
                content_type=cto,
                object_id=oid,
            )

        return qs.order_by("-timestamp")

    def perform_destroy(self, instance):
        # Only the reaction actor can delete it.
        if instance.name_id != self.request.user.id:
            raise PermissionError("Forbidden")

        cto = instance.content_type
        obj_id = instance.object_id
        owner_user_id = _get_target_owner_user_id(
            cto,
            obj_id,
            request_user_id=self.request.user.id,
        )
        had_message = _reaction_has_message(instance)

        super().perform_destroy(instance)

        # Broadcast only after the delete is committed.
        transaction.on_commit(
            lambda: _broadcast_target_summary(
                cto,
                obj_id,
                request_user=self.request.user,
            )
        )

        if had_message:
            transaction.on_commit(
                lambda: _broadcast_owner_inbox_changed(
                    cto=cto,
                    obj_id=obj_id,
                    owner_user_id=owner_user_id,
                    action_name="removed",
                    reaction=None,
                )
            )

    def create(self, request, *args, **kwargs):
        """
        Toggle a reaction with Boundary enforcement.

        Rules:
        - Same reaction exists: remove it.
        - New or changed reaction: enforce Boundary first.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        ct = serializer.validated_data["content_type"]
        oid = serializer.validated_data["object_id"]
        rtype = serializer.validated_data["reaction_type"]

        owner_user_id = _get_target_owner_user_id(
            ct,
            oid,
            request_user_id=request.user.id,
        )

        # Toggle off the same reaction.
        existing_same = (
            Reaction.objects
            .filter(
                name=user,
                content_type=ct,
                object_id=oid,
                reaction_type=rtype,
            )
            .first()
        )

        if existing_same:
            had_message = _reaction_has_message(existing_same)
            existing_same.delete()

            transaction.on_commit(
                lambda: _broadcast_target_summary(
                    ct,
                    oid,
                    request_user=request.user,
                )
            )

            if had_message:
                transaction.on_commit(
                    lambda: _broadcast_owner_inbox_changed(
                        cto=ct,
                        obj_id=oid,
                        owner_user_id=owner_user_id,
                        action_name="removed",
                        reaction=None,
                    )
                )

            return Response(status=status.HTTP_204_NO_CONTENT)

        # Enforce Boundary before creating or changing a reaction.
        boundary_check = check_reaction_create_boundary(
            actor=request.user,
            content_type=ct,
            object_id=oid,
        )

        if not boundary_check.allowed:
            return Response(
                content_interaction_error_payload(
                    message=boundary_check.message,
                    code=boundary_check.code,
                ),
                status=status.HTTP_403_FORBIDDEN,
            )

        # Load previous reactions before deleting them.
        previous_reactions = (
            Reaction.objects
            .filter(
                name=user,
                content_type=ct,
                object_id=oid,
            )
            .exclude(reaction_type=rtype)
        )

        previous_with_message_exists = _queryset_has_message(
            previous_reactions
        )

        previous_reactions.delete()

        # Create the new reaction.
        instance = serializer.save()
        out = self.get_serializer(instance)
        has_message = _reaction_has_message(instance)

        transaction.on_commit(
            lambda: _broadcast_target_summary(
                ct,
                oid,
                request_user=request.user,
            )
        )

        if previous_with_message_exists or has_message:
            transaction.on_commit(
                lambda: _broadcast_owner_inbox_changed(
                    cto=ct,
                    obj_id=oid,
                    owner_user_id=owner_user_id,
                    action_name=(
                        "changed"
                        if previous_with_message_exists
                        else "added"
                    ),
                    reaction=instance if has_message else None,
                )
            )

        return Response(
            out.data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="summary",
        permission_classes=[AllowAny],
    )
    def summary(self, request):
        """
        Count reactions by type for a target.
        """
        ct = request.query_params.get("content_type")
        oid = request.query_params.get("object_id")

        if not ct or not oid:
            return Response(
                {"detail": "content_type and object_id required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            if str(ct).isdigit():
                cto = ContentType.objects.get(pk=int(ct))
            elif "." in str(ct):
                app_label, model = str(ct).split(".", 1)
                cto = ContentType.objects.get(
                    app_label=app_label,
                    model=model,
                )
            else:
                cto = ContentType.objects.get(model=str(ct))
        except ContentType.DoesNotExist:
            return Response(
                {"detail": "Invalid content type"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = (
            Reaction.objects
            .filter(
                content_type=cto,
                object_id=oid,
            )
            .values("reaction_type")
            .annotate(count=models.Count("id"))
        )

        return Response(
            list(qs),
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="mine",
        permission_classes=[IsAuthenticated],
    )
    def mine(self, request):
        """
        List the current user's reactions.
        """
        qs = self.get_queryset().filter(name=request.user)
        page = self.paginate_queryset(qs)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(
        detail=False,
        methods=["get"],
        url_path="with-message",
        permission_classes=[IsAuthenticated],
    )
    def with_message(self, request):
        """
        Owner-only reactions containing non-blank messages.

        GET ?content_type=app.model|id|model&object_id=42
        """
        ct_param = request.query_params.get("content_type")
        obj_id = request.query_params.get("object_id")
        rtype = request.query_params.get("reaction_type")

        if not ct_param or not obj_id:
            return Response(
                {"detail": "content_type and object_id required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Resolve ContentType from ID, app.model or model.
        try:
            if str(ct_param).isdigit():
                cto = ContentType.objects.get(pk=int(ct_param))
            elif "." in str(ct_param):
                app_label, model = str(ct_param).split(".", 1)
                cto = ContentType.objects.get(
                    app_label=app_label,
                    model=model,
                )
            else:
                cto = ContentType.objects.get(model=str(ct_param))
        except ContentType.DoesNotExist:
            return Response(
                {"detail": "Invalid content type"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        model_cls = cto.model_class()
        if model_cls is None:
            return Response(
                {"detail": "Target model is unavailable"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            obj_pk = int(obj_id)
        except (TypeError, ValueError):
            obj_pk = obj_id

        try:
            target_obj = model_cls._default_manager.get(pk=obj_pk)
        except model_cls.DoesNotExist:
            return Response(
                {"detail": "Target object not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        owner_id = _resolve_owner_user_id(
            target_obj,
            request_user_id=request.user.id,
        )

        if owner_id != request.user.id:
            return Response(
                {"detail": "Forbidden"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Filter NULL in SQL and blank decrypted values in Python.
        qs = (
            Reaction.objects
            .filter(
                content_type=cto,
                object_id=obj_pk,
            )
            .exclude(message__isnull=True)
            .select_related(
                "name",
                "name__label",
                "name__member_profile",
            )
            .order_by("-timestamp")
        )

        if rtype:
            qs = qs.filter(reaction_type=rtype)

        items = []

        for reaction in qs[:200]:
            if not _reaction_has_message(reaction):
                continue

            user_data = SimpleCustomUserSerializer(
                reaction.name,
                context={"request": request},
            ).data

            items.append(
                {
                    "id": reaction.id,
                    "reaction_type": reaction.reaction_type,
                    "message": reaction.message,
                    "timestamp": reaction.timestamp,
                    "user": user_data,
                }
            )

        return Response(
            items,
            status=status.HTTP_200_OK,
        )