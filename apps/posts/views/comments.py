# apps/posts/views/comments.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import PermissionDenied
from django.contrib.contenttypes.models import ContentType
from django.db.models import Prefetch
from django.db import transaction
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import logging
from django.core.exceptions import ObjectDoesNotExist

from django.db.models import Prefetch, Count
from apps.core.pagination import ConfigurablePagination
from apps.posts.models.comment import Comment
from apps.posts.serializers.comments import (
    CommentReadSerializer,
    CommentWriteSerializer,
    RootCommentReadSerializer,
    SimpleCommentReadSerializer
)
from apps.posts.services.boundary_interactions import (
    check_comment_create_boundary,
    check_comment_update_boundary,
    content_interaction_error_payload,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------
# Helper for WS grouping
def comment_group_name(ct_id: int, obj_id: int) -> str:
    """Group name for comment WebSocket broadcasts."""
    return f"comments.{ct_id}.{obj_id}"


# ---------------------------------------------------------------------
def _resolve_content_type(ct: str):
    """
    Accepts:
      - numeric id: '23'
      - dotted 'app.model': 'posts.comment'
      - plain model: 'comment'
    Returns ContentType or raises ContentType.DoesNotExist.
    """
    if str(ct).isdigit():
        return ContentType.objects.get(pk=int(ct))
    if "." in str(ct):
        app_label, model = str(ct).split(".", 1)
        return ContentType.objects.get(app_label=app_label, model=model)
    return ContentType.objects.get(model=str(ct))


# ---------------------------------------------------------------------
def _safe_broadcast(event_name: str, payload: dict, ct_id: int, obj_id: int):
    """
    Send WS event safely (won't break HTTP if Redis/Channels is down).
    """
    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            logger.warning("Channel layer not configured; skip WS send.")
            return

        group = comment_group_name(ct_id, obj_id)

        async_to_sync(channel_layer.group_send)(
            group,
            {
                "type": "dispatch_event",  
                "app": "comments",        
                "event": event_name,
                "data": payload,
            },
        )

    except Exception:
        logger.exception("WS broadcast failed (ignored)")
        

# ---------------------------------------------------------------------
def _comment_realtime_payload(instance: Comment, serialized: dict | None = None) -> dict:
    """
    Canonical realtime payload for comment events.

    Important for iOS:
    - content_type_id is required for legacy numeric subscriptions.
    - content_type is required for clients that only know app.model.
    - object_id is required to route the event to the visible target.
    - recomment / parent_id / is_reply are required to distinguish roots/replies.
    """
    data = dict(serialized or {})

    ct = instance.content_type
    data["content_type_id"] = instance.content_type_id
    data["ct_id"] = instance.content_type_id
    data["content_type"] = f"{ct.app_label}.{ct.model}" if ct else None
    data["object_id"] = instance.object_id
    data["id"] = instance.id
    data["recomment"] = instance.recomment_id
    data["parent_id"] = instance.recomment_id
    data["is_reply"] = instance.recomment_id is not None

    return data

# ---------------------------------------------------------------------
def _deleted_comment_realtime_payload(
    *,
    comment_id: int,
    content_type_id: int,
    content_type_label: str | None,
    object_id: int,
    parent_id: int | None,
) -> dict:
    return {
        "id": comment_id,
        "content_type_id": content_type_id,
        "ct_id": content_type_id,
        "content_type": content_type_label,
        "object_id": object_id,
        "recomment": parent_id,
        "parent_id": parent_id,
        "is_reply": parent_id is not None,
    }

# ---------------------------------------------------------------------
class CommentViewSet(viewsets.ModelViewSet):
    """
    🔹 REST + WebSocket broadcast for comments.
    - GET    /posts/comments/?content_type=app.model|model|id&object_id=42
    - GET    /posts/comments/thread/?content_type=...&object_id=...
    - POST   /posts/comments/
    - PATCH  /posts/comments/<id>/
    - DELETE /posts/comments/<id>/
    - GET    /posts/comments/summary/?content_type=...&object_id=...
    """
    queryset = (
        Comment.objects.all()
        .select_related("name", "content_type")
        .order_by("-published_at")
    )
    permission_classes = [IsAuthenticated]
    pagination_class = ConfigurablePagination

    # ---------------------------------------------------------------------
    # Permissions
    # ---------------------------------------------------------------------
    def _is_content_owner(self, instance: Comment, user) -> bool:
        user_id = getattr(user, "id", None)
        if not user_id:
            return False

        try:
            target = instance.content_type.get_object_for_this_type(
                pk=instance.object_id
            )
        except ObjectDoesNotExist:
            return False
        except Exception:
            logger.exception("Failed to resolve comment target for ownership check")
            return False

        owner_field_candidates = [
            "name_id",
            "user_id",
            "owner_id",
            "author_id",
            "created_by_id",
        ]

        for field_name in owner_field_candidates:
            if getattr(target, field_name, None) == user_id:
                return True

        nested_owner_candidates = [
            "name",
            "user",
            "owner",
            "author",
            "created_by",
        ]

        for field_name in nested_owner_candidates:
            owner = getattr(target, field_name, None)
            if getattr(owner, "id", None) == user_id:
                return True

        return False


    def _check_delete_permission(self, instance: Comment, user):
        if instance.name_id == getattr(user, "id", None):
            return

        if self._is_content_owner(instance, user):
            return

        raise PermissionDenied("You are not allowed to delete this comment.")

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return CommentWriteSerializer
        return CommentReadSerializer

    # Override create -----------------------------------------------------------
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
        except Exception:
            logger.warning(
                "Comment validation failed",
                exc_info=True,
                extra={"data": request.data},
            )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # ------------------------------------------------------------
        # Boundary enforcement
        # ------------------------------------------------------------
        content_type = serializer.validated_data.get("content_type")
        object_id = serializer.validated_data.get("object_id")
        parent_comment = serializer.validated_data.get("recomment")

        boundary_check = check_comment_create_boundary(
            actor=request.user,
            content_type=content_type,
            object_id=object_id,
            parent_comment=parent_comment,
        )

        if not boundary_check.allowed:
            return Response(
                content_interaction_error_payload(
                    message=boundary_check.message,
                    code=boundary_check.code,
                ),
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            self.perform_create(serializer)

        except PermissionDenied as pd:
            logger.warning("Permission denied on create", exc_info=True)
            return Response({"detail": str(pd)}, status=status.HTTP_403_FORBIDDEN)

        except Exception:
            logger.exception("Comment create crashed", extra={"data": request.data})
            return Response(
                {"detail": "Internal server error while creating comment."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        read_data = CommentReadSerializer(
            serializer.instance,
            context=self.get_serializer_context(),
        ).data

        return Response(read_data, status=status.HTTP_201_CREATED)
    
    # Override update -----------------------------------------------------------
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()

        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
        )

        try:
            serializer.is_valid(raise_exception=True)
        except Exception:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # ------------------------------------------------------------
        # Owner check first
        # ------------------------------------------------------------
        try:
            self._check_owner(instance, self.request.user)
        except PermissionDenied as pd:
            return Response({"detail": str(pd)}, status=status.HTTP_403_FORBIDDEN)

        # ------------------------------------------------------------
        # Boundary enforcement
        # Editing an old comment is treated as renewed interaction.
        # Deleting remains allowed in perform_destroy.
        # ------------------------------------------------------------
        boundary_check = check_comment_update_boundary(
            actor=request.user,
            comment=instance,
        )

        if not boundary_check.allowed:
            return Response(
                content_interaction_error_payload(
                    message=boundary_check.message,
                    code=boundary_check.code,
                ),
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            self.perform_update(serializer)

        except PermissionDenied as pd:
            return Response({"detail": str(pd)}, status=status.HTTP_403_FORBIDDEN)

        except Exception:
            logger.exception("Comment update crashed", extra={"data": request.data})
            return Response(
                {"detail": "Internal server error while updating comment."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        read_data = CommentReadSerializer(
            serializer.instance,
            context=self.get_serializer_context(),
        ).data

        return Response(read_data, status=status.HTTP_200_OK)
    
    # -----------------------------------------------------------------
    # Core QuerySet filter
    def get_queryset(self):
        qs = super().get_queryset()
        ct = self.request.query_params.get("content_type")
        oid = self.request.query_params.get("object_id")

        if ct and oid:
            try:
                cto = _resolve_content_type(ct)
            except ContentType.DoesNotExist:
                return Comment.objects.none()

            # object_id ممکنه رشته‌ای بیاد؛ cast امن
            try:
                oid_int = int(oid)
            except (TypeError, ValueError):
                oid_int = oid
            qs = qs.filter(content_type=cto, object_id=oid_int)

        return qs

    # -----------------------------------------------------------------
    # Owner control
    def _check_owner(self, instance: Comment, user):
        if instance.name_id != getattr(user, "id", None):
            raise PermissionDenied("You are not allowed to modify this comment.")

    # -----------------------------------------------------------------
    # Create with WS broadcast (safe)
    def perform_create(self, serializer):
        inst: Comment = serializer.save()

        serialized = CommentReadSerializer(
            inst,
            context=self.get_serializer_context(),
        ).data

        data = _comment_realtime_payload(
            inst,
            serialized=serialized,
        )

        transaction.on_commit(
            lambda: _safe_broadcast(
                "created",
                data,
                inst.content_type_id,
                inst.object_id,
            )
        )

    # -----------------------------------------------------------------
    # Update with WS broadcast (safe)
    def perform_update(self, serializer):
        inst: Comment = serializer.save()

        serialized = CommentReadSerializer(
            inst,
            context=self.get_serializer_context(),
        ).data

        data = _comment_realtime_payload(
            inst,
            serialized=serialized,
        )

        transaction.on_commit(
            lambda: _safe_broadcast(
                "updated",
                data,
                inst.content_type_id,
                inst.object_id,
            )
        )

    # -----------------------------------------------------------------
    # Delete with WS broadcast (safe)
    def perform_destroy(self, instance: Comment):
        self._check_delete_permission(instance, self.request.user)

        ct_id = instance.content_type_id
        oid = instance.object_id
        cid = instance.id
        parent_id = instance.recomment_id

        ct = instance.content_type
        ct_label = f"{ct.app_label}.{ct.model}" if ct else None

        payload = _deleted_comment_realtime_payload(
            comment_id=cid,
            content_type_id=ct_id,
            content_type_label=ct_label,
            object_id=oid,
            parent_id=parent_id,
        )

        instance.delete()

        transaction.on_commit(
            lambda: _safe_broadcast(
                "deleted",
                payload,
                ct_id,
                oid,
            )
        )
        
    
    # -----------------------------------------------------------------
    # THREAD — all top-level comments + 1-level replies
    @action(
        detail=False,
        methods=["get"],
        url_path="thread",
        permission_classes=[AllowAny],
    )
    def thread(self, request):
        """Public endpoint: list root comments with replies."""
        ct = request.query_params.get("content_type")
        oid = request.query_params.get("object_id")
        if not ct or not oid:
            return Response(
                {"detail": "content_type and object_id required"}, status=400
            )

        try:
            cto = _resolve_content_type(ct)
        except ContentType.DoesNotExist:
            return Response({"detail": "Invalid content type"}, status=400)

        try:
            oid_int = int(oid)
        except (TypeError, ValueError):
            oid_int = oid

        roots = (
            Comment.objects.filter(
                content_type=cto, object_id=oid_int, recomment__isnull=True
            )
            .select_related("name", "content_type")
            .prefetch_related(
                Prefetch(
                    "responses",
                    queryset=Comment.objects.select_related("name").order_by(
                        "published_at"
                    ),
                )
            )
            .order_by("-published_at")
        )
        data = CommentReadSerializer(
            roots, many=True, context=self.get_serializer_context()
        ).data
        return Response(data, status=200)

    # -----------------------------------------------------------------
    # SUMMARY — counts
    @action(
        detail=False,
        methods=["get"],
        url_path="summary",
        permission_classes=[AllowAny],
    )
    def summary(self, request):
        """
        Return root comment count, reply count, and total interaction count
        for an object.

        comments = root comments only
        replies = one-level replies only
        total = comments + replies
        """
        ct = request.query_params.get("content_type")
        oid = request.query_params.get("object_id")

        if not ct or not oid:
            return Response(
                {"detail": "content_type and object_id required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            cto = _resolve_content_type(ct)
        except ContentType.DoesNotExist:
            return Response(
                {"detail": "Invalid content type"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            oid_int = int(oid)
        except (TypeError, ValueError):
            oid_int = oid

        base_qs = Comment.objects.filter(
            content_type=cto,
            object_id=oid_int,
        )

        root_comments = base_qs.filter(
            recomment__isnull=True,
        ).count()

        replies = base_qs.filter(
            recomment__isnull=False,
        ).count()

        return Response(
            {
                "comments": root_comments,
                "replies": replies,
                "total": root_comments + replies,
            },
            status=status.HTTP_200_OK,
        )


    # -----------------------------------------------------------------
    # THREAD_PAGE — paginated roots ONLY (no replies), with replies_count
    @action(
        detail=False,
        methods=["get"],
        url_path="thread_page",
        permission_classes=[AllowAny],
    )
    def thread_page(self, request):
        """
        Public endpoint: list root comments (paginated) WITHOUT replies.
        """

        # 👇 page size مخصوص همین اکشن
        self.pagination_page_size = 10

        ct = request.query_params.get("content_type")
        oid = request.query_params.get("object_id")
        if not ct or not oid:
            return Response(
                {"detail": "content_type and object_id required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            cto = _resolve_content_type(ct)
        except ContentType.DoesNotExist:
            return Response(
                {"detail": "Invalid content type"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            oid_int = int(oid)
        except (TypeError, ValueError):
            oid_int = oid

        # ------------------------------------------------------------
        # ROOT comments only (no replies)
        # ------------------------------------------------------------
        qs = (
            Comment.objects
            .filter(
                content_type=cto,
                object_id=oid_int,
                recomment__isnull=True,
            )
            .select_related("name", "content_type")
            .annotate(replies_count=Count("responses"))
            .order_by("-published_at")
        )

        # ------------------------------------------------------------
        # Pagination (CORE-AWARE)
        # ------------------------------------------------------------
        page = self.paginate_queryset(qs)
        serializer = RootCommentReadSerializer(
            page,
            many=True,
            context=self.get_serializer_context(),
        )
        return self.get_paginated_response(serializer.data)


    # -----------------------------------------------------------------
    # REPLIES — paginated replies for a given root comment
    @action(
        detail=False,
        methods=["get"],
        url_path="replies",
        permission_classes=[AllowAny],
    )
    def replies(self, request):
        """
        Public endpoint: list replies (paginated) of a given root comment.
        """

        # 👇 page size مخصوص replies
        self.pagination_page_size = 10

        parent_id = request.query_params.get("parent_id")
        if not parent_id:
            return Response(
                {"detail": "parent_id required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            parent_id = int(parent_id)
        except (TypeError, ValueError):
            return Response(
                {"detail": "parent_id must be integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ------------------------------------------------------------
        # Replies (1-level only), oldest first
        # ------------------------------------------------------------
        qs = (
            Comment.objects
            .filter(recomment_id=parent_id)
            .select_related("name")
            .order_by("published_at")
        )

        # ------------------------------------------------------------
        # Pagination (CORE-AWARE)
        # ------------------------------------------------------------
        page = self.paginate_queryset(qs)
        serializer = SimpleCommentReadSerializer(
            page,
            many=True,
            context=self.get_serializer_context(),
        )
        return self.get_paginated_response(serializer.data)
