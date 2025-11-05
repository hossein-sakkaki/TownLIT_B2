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

from django.db.models import Prefetch, Count
from apps.core.pagination import ConfigurablePagination
from apps.posts.models import Comment
from apps.posts.serializers.comments import (
    CommentReadSerializer,
    CommentWriteSerializer,
    RootCommentReadSerializer,
    SimpleCommentReadSerializer
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------
# Helper for WS grouping
def comment_group_name(ct_id: int, obj_id: int) -> str:
    """Group name for comment WebSocket broadcasts."""
    return f"comments.{ct_id}.{obj_id}"


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
            {"type": "comment.event", "event": event_name, "data": payload},
        )
    except Exception:
        logger.exception("WS broadcast failed (ignored)")
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

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return CommentWriteSerializer
        return CommentReadSerializer

    # Override create -----------------------------------------------------------
    def create(self, request, *args, **kwargs):
        logger.info("POST /posts/comments/ incoming", extra={"data": request.data})
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as ex:
            # validation errors → 400 with details
            logger.warning("Comment validation failed", exc_info=True, extra={"data": request.data})
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            self.perform_create(serializer)
        except PermissionDenied as pd:
            logger.warning("Permission denied on create", exc_info=True)
            return Response({"detail": str(pd)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as ex:
            # real 500, but log with context
            logger.exception("Comment create crashed", extra={"data": request.data})
            return Response(
                {"detail": "Internal server error while creating comment."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # respond with read-serializer (unified)
        read_data = CommentReadSerializer(serializer.instance, context=self.get_serializer_context()).data
        return Response(read_data, status=status.HTTP_201_CREATED)
    
    # Override update -----------------------------------------------------------
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            self.perform_update(serializer)
        except PermissionDenied as pd:
            return Response({"detail": str(pd)}, status=status.HTTP_403_FORBIDDEN)
        except Exception:
            logger.exception("Comment update crashed", extra={"data": request.data})
            return Response({"detail": "Internal server error while updating comment."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        read_data = CommentReadSerializer(serializer.instance, context=self.get_serializer_context()).data
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
        # Serialize once
        data = CommentReadSerializer(
            inst, context=self.get_serializer_context()
        ).data

        # Broadcast AFTER commit, safely
        transaction.on_commit(lambda: _safe_broadcast(
            "created", data, inst.content_type_id, inst.object_id
        ))

    # -----------------------------------------------------------------
    # Update with WS broadcast (safe)
    def perform_update(self, serializer):
        inst: Comment = serializer.instance
        self._check_owner(inst, self.request.user)
        inst = serializer.save()

        data = CommentReadSerializer(
            inst, context=self.get_serializer_context()
        ).data

        transaction.on_commit(lambda: _safe_broadcast(
            "updated", data, inst.content_type_id, inst.object_id
        ))

    # -----------------------------------------------------------------
    # Delete with WS broadcast (safe)
    def perform_destroy(self, instance: Comment):
        self._check_owner(instance, self.request.user)
        ct_id, oid, cid = instance.content_type_id, instance.object_id, instance.id
        instance.delete()

        transaction.on_commit(lambda: _safe_broadcast(
            "deleted", {"id": cid}, ct_id, oid
        ))

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
        """Return total counts of comments and replies for an object."""
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

        total_comments = Comment.objects.filter(
            content_type=cto, object_id=oid_int
        ).count()
        total_replies = Comment.objects.filter(
            content_type=cto, object_id=oid_int, recomment__isnull=False
        ).count()

        return Response(
            {
                "comments": total_comments,
                "replies": total_replies,
                "total": total_comments + total_replies,
            },
            status=200,
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
        - Params:
            content_type: app.model | model | id
            object_id: int
            page_size: optional (default 10 for this endpoint)
            page: optional (PageNumberPagination)
        - Returns: paginated response with 'results' of RootCommentReadSerializer
        """
        ct = request.query_params.get("content_type")
        oid = request.query_params.get("object_id")
        if not ct or not oid:
            return Response({"detail": "content_type and object_id required"}, status=400)

        try:
            cto = _resolve_content_type(ct)
        except ContentType.DoesNotExist:
            return Response({"detail": "Invalid content type"}, status=400)

        try:
            oid_int = int(oid)
        except (TypeError, ValueError):
            oid_int = oid

        # Base queryset for ROOTS only (no replies)
        roots_qs = (
            Comment.objects.filter(
                content_type=cto, object_id=oid_int, recomment__isnull=True
            )
            .select_related("name", "content_type")
            # Annotate replies_count to avoid N+1 queries in serializer
            .annotate(replies_count=Count("responses"))
            .order_by("-published_at")
        )

        # Use configurable pagination with default page_size=10 for THIS endpoint
        default_size = 10
        try:
            size_param = int(request.query_params.get("page_size", default_size))
        except (TypeError, ValueError):
            size_param = default_size

        paginator = ConfigurablePagination(page_size=size_param, max_page_size=50)
        page = paginator.paginate_queryset(roots_qs, request)
        ser = RootCommentReadSerializer(page, many=True, context=self.get_serializer_context())
        return paginator.get_paginated_response(ser.data)


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
        - Params:
            parent_id: required (the root comment ID)
            page_size: optional (default 10)
            page: optional
        - Returns: paginated response with 'results' of SimpleCommentReadSerializer
        """
        parent_id = request.query_params.get("parent_id")
        if not parent_id:
            return Response({"detail": "parent_id required"}, status=400)

        try:
            parent_id = int(parent_id)
        except (TypeError, ValueError):
            return Response({"detail": "parent_id must be integer"}, status=400)

        # Replies of that root (1-level), oldest-first
        replies_qs = (
            Comment.objects.filter(recomment_id=parent_id)
            .select_related("name")
            .order_by("published_at")
        )

        default_size = 10
        try:
            size_param = int(request.query_params.get("page_size", default_size))
        except (TypeError, ValueError):
            size_param = default_size

        paginator = ConfigurablePagination(page_size=size_param, max_page_size=50)
        page = paginator.paginate_queryset(replies_qs, request)
        ser = SimpleCommentReadSerializer(page, many=True, context=self.get_serializer_context())
        return paginator.get_paginated_response(ser.data)
