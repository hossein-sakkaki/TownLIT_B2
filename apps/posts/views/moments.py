# apps/posts/views/moments.py

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.db.models import F, Q

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework import status

from apps.posts.models.moment import Moment
from apps.posts.serializers.moments import MomentSerializer
from apps.core.visibility.query import VisibilityQuery
from apps.core.visibility.policy import VisibilityPolicy
from apps.core.pagination import ConfigurablePagination, FeedCursorPagination

from apps.core.feed.trending import TrendingEngine
from apps.core.feed.hybrid import HybridFeedEngine
from apps.core.feed.personalized_trending import PersonalizedTrendingEngine
from apps.core.ownership.owner_gate_mixins import OwnerGateMixin
from apps.core.ownership.utils import resolve_owner_from_request
from apps.core.visibility.constants import VISIBILITY_GLOBAL

import logging
logger = logging.getLogger(__name__)


class MomentViewSet(OwnerGateMixin, viewsets.ModelViewSet):
    """
    Moment API
    -------------------------
    - visibility-aware
    - owner-safe
    - feed: cursor-based pagination
    - explore / me: page-number pagination
    """
    serializer_class = MomentSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "slug"
    pagination_class = ConfigurablePagination
    pagination_page_size = 12

    # -------------------------------------------------
    # Permissions
    # -------------------------------------------------
    def get_permissions(self):
        """
        Allow public access only for safe read actions.
        """
        if self.action in [
            "retrieve",
            "explore",
            "trending",
        ]:
            return [AllowAny()]

        return super().get_permissions()

    # -------------------------------------------------
    # Base queryset
    # -------------------------------------------------
    def get_queryset(self):
        base = (
            Moment.objects
            .select_related("content_type")
            .order_by("-published_at", "-id")
        )

        # Retrieve stays open, gating happens later
        if self.action == "retrieve":
            return base

        if not self.request.user or not self.request.user.is_authenticated:
            qs = base.filter(visibility=VISIBILITY_GLOBAL)
        else:
            qs = VisibilityQuery.for_viewer(
                viewer=self.request.user,
                base_queryset=base,
            )

        # Visitors must never see not-yet-converted videos
        if not self.request.user.is_authenticated:
            qs = qs.exclude(
                Q(video__isnull=False) & ~Q(is_converted=True)
            )

        return qs

    # -------------------------------------------------
    # Owner resolution
    # -------------------------------------------------
    def _get_request_owner(self):
        """Resolve active owner profile from request."""
        return resolve_owner_from_request(self.request)

    def _assert_is_owner(self, obj):
        owner = self._get_request_owner()
        if not owner:
            raise PermissionDenied("Invalid owner context.")

        owner_ct = ContentType.objects.get_for_model(owner.__class__)

        if (
            obj.content_type_id != owner_ct.id
            or obj.object_id != owner.id
        ):
            raise PermissionDenied("You do not own this Moment.")

    # -------------------------------------------------
    # Create
    # -------------------------------------------------
    def perform_create(self, serializer):
        owner = self._get_request_owner()

        if not owner:
            raise PermissionDenied(
                "Only members or guest users can create moments."
            )

        serializer.save(
            content_type=ContentType.objects.get_for_model(owner.__class__),
            object_id=owner.id,
        )

    # -------------------------------------------------
    # Update
    # -------------------------------------------------
    def perform_update(self, serializer):
        obj = self.get_object()
        self._assert_is_owner(obj)

        serializer.save(
            updated_at=timezone.now()
        )

    # -------------------------------------------------
    # Delete
    # -------------------------------------------------
    def perform_destroy(self, instance):
        self._assert_is_owner(instance)
        instance.delete()

    # -------------------------------------------------
    # Feed
    # -------------------------------------------------
    @action(
        detail=False,
        methods=["get"],
        pagination_class=FeedCursorPagination,
    )
    def feed(self, request):
        qs = HybridFeedEngine.apply(
            self.get_queryset(),
            viewer=request.user,
        )
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    # -------------------------------------------------
    # Trending for me
    # -------------------------------------------------
    @action(
        detail=False,
        methods=["get"],
        pagination_class=FeedCursorPagination,
    )
    def trending_for_me(self, request):
        qs = PersonalizedTrendingEngine.apply(
            self.get_queryset(),
            viewer=request.user,
        )
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    # -------------------------------------------------
    # Trending
    # -------------------------------------------------
    @action(
        detail=False,
        methods=["get"],
        pagination_class=FeedCursorPagination,
        permission_classes=[AllowAny],
    )
    def trending(self, request):
        qs = TrendingEngine.apply(
            self.get_queryset(),
            window_seconds=24 * 60 * 60,
        )
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    # -------------------------------------------------
    # My moments
    # -------------------------------------------------
    @action(detail=False, methods=["get"])
    def me(self, request):
        owner = self._get_request_owner()
        if not owner:
            raise PermissionDenied("Invalid owner type.")

        owner_ct = ContentType.objects.get_for_model(owner.__class__)

        qs = self.get_queryset().filter(
            content_type_id=owner_ct.id,
            object_id=owner.id,
        )

        try:
            page = self.paginate_queryset(qs)
        except NotFound:
            return Response(
                {
                    "count": qs.count(),
                    "next": None,
                    "previous": None,
                    "results": [],
                }
            )

        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    # -------------------------------------------------
    # Explore
    # -------------------------------------------------
    @action(
        detail=False,
        methods=["get"],
        permission_classes=[AllowAny],
    )
    def explore(self, request):
        qs = (
            self.get_queryset()
            .filter(visibility=VISIBILITY_GLOBAL)
        )

        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    # -------------------------------------------------
    # Retrieve
    # -------------------------------------------------
    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()

        # Hard owner-level gate
        self.apply_hard_owner_gate(request, obj)

        # Not-yet-converted video is owner-only
        if obj.video and obj.is_converted is not True:
            owner = resolve_owner_from_request(request) if request.user.is_authenticated else None
            if not owner:
                raise NotFound("Moment not found.")

            owner_ct = ContentType.objects.get_for_model(owner.__class__)
            is_owner = (
                obj.content_type_id == owner_ct.id
                and obj.object_id == owner.id
            )
            if not is_owner:
                raise NotFound("Moment not found.")

        # Visibility gate
        reason = VisibilityPolicy.gate_reason(viewer=request.user, obj=obj)
        if reason is not None:
            return Response(
                {
                    "detail": "Access restricted.",
                    "code": reason,
                    "content_type": "moment",
                    "slug": obj.slug,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Analytics
        try:
            Moment.objects.filter(pk=obj.pk).update(
                view_count_internal=F("view_count_internal") + 1,
                last_viewed_at=timezone.now(),
            )
        except Exception:
            logger.exception("moment analytics update failed")

        serializer = self.get_serializer(obj)
        return Response(serializer.data)