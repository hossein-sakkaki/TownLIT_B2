# apps/posts/views/testimonies.py

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone
from django.db.models import F

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, AllowAny    

from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from apps.posts.models.testimony import Testimony
from apps.posts.serializers.testimonies import TestimonySerializer
from apps.core.visibility.query import VisibilityQuery
from apps.core.pagination import ConfigurablePagination, FeedCursorPagination
from apps.core.visibility.policy import VisibilityPolicy
from apps.core.ownership.utils import resolve_owner_from_request
import logging
logger = logging.getLogger(__name__)


class TestimonyViewSet(viewsets.ModelViewSet):
    """
    Testimony API (post-like)

    - Visibility-aware
    - Interaction-ready
    - Cursor feed support
    - Owner-safe
    """

    serializer_class = TestimonySerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "slug"
    lookup_url_kwarg = "slug" 
    pagination_class = ConfigurablePagination
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    # -------------------------------------------------
    # Permissions (Visitor-safe)
    # -------------------------------------------------
    def get_permissions(self):
        """
        Allow public access ONLY for safe read actions.
        """
        if self.action in [
            "retrieve",   # public watch page needs this
            "explore",    # public discover
        ]:
            return [AllowAny()]

        return super().get_permissions()

    # -------------------------------------------------
    # Base queryset (ordering only)
    # -------------------------------------------------
    def get_queryset(self):
        base = (
            Testimony.objects
            .select_related("content_type")
            .order_by("-published_at", "-id")
        )

        # IMPORTANT: retrieve must not be pre-filtered by Query
        if self.action == "retrieve":
            return base

        # public explore (visitor-safe)
        if self.action == "explore" and not self.request.user.is_authenticated:
            return base.filter(visibility="global")  # keep existing behavior

        # IMPORTANT: Query should use request.user for consistency
        return VisibilityQuery.for_viewer(
            viewer=self.request.user,
            base_queryset=base,
        )



    # -------------------------------------------------
    # Owner resolver
    # -------------------------------------------------
    def _get_owner(self):
        return resolve_owner_from_request(self.request)


    def _assert_is_owner(self, obj):
        owner = self._get_owner()
        if not owner:
            raise PermissionDenied("Invalid owner context.")

        owner_ct = ContentType.objects.get_for_model(owner.__class__)
        if (
            obj.content_type_id != owner_ct.id
            or obj.object_id != owner.id
        ):
            raise PermissionDenied("You do not own this Testimony.")

    # -------------------------------------------------
    # Create
    # -------------------------------------------------
    @transaction.atomic
    def perform_create(self, serializer):
        owner = self._get_owner()
        if not owner:
            raise PermissionDenied("Invalid owner type.")

        ttype = serializer.validated_data.get("type")

        owner_ct = ContentType.objects.get_for_model(owner.__class__)

        # Enforce: one testimony per type per owner
        exists = Testimony.objects.filter(
            content_type=owner_ct,
            object_id=owner.id,
            type=ttype,
        ).exists()

        if exists:
            raise PermissionDenied(
                f"You already have a '{ttype}' testimony."
            )

        serializer.save(
            content_type=owner_ct,
            object_id=owner.id,
        )

    # -------------------------------------------------
    # Update
    # -------------------------------------------------
    def perform_update(self, serializer):
        obj = self.get_object()
        self._assert_is_owner(obj)
        serializer.save(updated_at=timezone.now())

    # -------------------------------------------------
    # Delete
    # -------------------------------------------------
    def perform_destroy(self, instance):
        self._assert_is_owner(instance)
        instance.delete()

    # -------------------------------------------------
    # Feed (cursor-based, home timeline)
    # -------------------------------------------------
    @action(
        detail=False,
        methods=["get"],
        pagination_class=FeedCursorPagination,
    )
    def feed(self, request):
        qs = self.get_queryset()
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    # -------------------------------------------------
    # My testimonies (owner-only)
    # -------------------------------------------------
    @action(detail=False, methods=["get"])
    def me(self, request):
        owner = self._get_owner()
        if not owner:
            raise PermissionDenied("Invalid owner type.")

        owner_ct = ContentType.objects.get_for_model(owner.__class__)

        qs = self.get_queryset().filter(
            content_type_id=owner_ct.id,
            object_id=owner.id,
        )

        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    # -------------------------------------------------
    # Explore (public discover)
    # -------------------------------------------------
    @action(
        detail=False,
        methods=["get"],
        permission_classes=[AllowAny],
    )
    def explore(self, request):
        qs = self.get_queryset()  # already visitor-safe
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)


    # -------------------------------------------------
    # Profile summary (1 per type)
    # -------------------------------------------------
    @action(detail=False, methods=["get"])
    def summary(self, request):
        owner = self._get_owner()
        if not owner:
            raise PermissionDenied("Invalid owner type.")

        owner_ct = ContentType.objects.get_for_model(owner.__class__)
        qs = Testimony.objects.filter(
            content_type=owner_ct,
            object_id=owner.id,
        )

        def pack(ttype):
            t = qs.filter(type=ttype).first()
            if not t:
                return {"exists": False}
            data = {
                "exists": True,
                "id": t.id,
                "slug": t.slug,
                "title": t.title,
                "published_at": t.published_at,
                "is_converted": t.is_converted,
            }
            if t.type == Testimony.TYPE_WRITTEN:
                excerpt = (
                    t.content[:140] + "…"
                    if t.content and len(t.content) > 140
                    else t.content
                )
                data["excerpt"] = excerpt
            return data

        return Response({
            "audio": pack(Testimony.TYPE_AUDIO),
            "video": pack(Testimony.TYPE_VIDEO),
            "written": pack(Testimony.TYPE_WRITTEN),
        })

    # -------------------------------------------------
    # Retrieve (public-safe, analytics counted)
    # -------------------------------------------------
    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()

        reason = VisibilityPolicy.gate_reason(viewer=request.user, obj=obj)
        if reason is not None:
            return Response(
                {
                    "detail": "Access restricted.",
                    "code": reason,  # "login_required" | "forbidden" | "hidden"
                    "content_type": "testimony",
                    "slug": obj.slug,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Analytics safe
        try:
            Testimony.objects.filter(pk=obj.pk).update(
                view_count_internal=F("view_count_internal") + 1,
                last_viewed_at=timezone.now(),
            )
        except Exception:
            logger.exception("🔥 testimony analytics update failed")

        serializer = self.get_serializer(obj)
        return Response(serializer.data)