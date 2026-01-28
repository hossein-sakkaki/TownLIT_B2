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
from apps.core.visibility.constants import VISIBILITY_GLOBAL


import logging
logger = logging.getLogger(__name__)

class MomentViewSet(OwnerGateMixin, viewsets.ModelViewSet):
    """
    Moment API
    -------------------------
    - visibility-aware (VisibilityQuery)
    - owner-safe (Member / Guest / future Organization)
    - feed: cursor-based pagination (Instagram-like)
    - explore / me: page-number pagination
    """
    serializer_class = MomentSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "slug"
    pagination_class = ConfigurablePagination
    pagination_page_size = 12

    # -------------------------------------------------
    # Permissions (Visitor-safe)
    # -------------------------------------------------
    def get_permissions(self):
        """
        Allow public (unauthenticated) access ONLY for safe read actions.
        """
        if self.action in [
            "retrieve",     # view a single moment
            "explore",      # public discover
            "trending",     # public trending
        ]:
            return [AllowAny()]

        return super().get_permissions()

    # -------------------------------------------------
    # Base queryset (NO visibility logic here)
    # -------------------------------------------------
    def get_queryset(self):
        base = (
            Moment.objects
            .select_related("content_type")
            .order_by("-published_at", "-id")
        )

        if self.action == "retrieve":
            return base

        if not self.request.user or not self.request.user.is_authenticated:
            qs = base.filter(visibility=VISIBILITY_GLOBAL)
        else:
            qs = VisibilityQuery.for_viewer(
                viewer=self.request.user,
                base_queryset=base,
            )

        if not self.request.user.is_authenticated:
            qs = qs.exclude(
                Q(video__isnull=False) & ~Q(is_converted=True)
            )

        return qs


    # -------------------------------------------------
    # Owner resolution (DRY)
    # -------------------------------------------------
    def _get_request_owner(self):
        user = self.request.user

        if hasattr(user, "member_profile"):
            return user.member_profile

        if hasattr(user, "guest_profile"):
            return user.guest_profile

        return None

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

        print("FILES:", self.request.FILES)
        print("DATA:", self.request.data)

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
    # Feed (home timeline – cursor based)
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
    # Trending for me (cursor based)
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
    # Trending (cursor based)
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
    # My moments (owner only)
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
    # Explore (public discover)
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
    # Retrieve (public-safe, analytics counted)
    # -------------------------------------------------
    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()

        # 0) HARD owner-level gate (your existing rule)
        self.apply_hard_owner_gate(request, obj)

        # -------------------------------------------------
        # 🔐 HARD DOMAIN RULE (retrieve)
        # If video is not converted, ONLY owner can access it.
        # Others get 404 (do not leak existence).
        # -------------------------------------------------
        if obj.video and obj.is_converted is not True:
            owner = self._get_request_owner() if request.user.is_authenticated else None
            if not owner:
                raise NotFound("Moment not found.")

            owner_ct = ContentType.objects.get_for_model(owner.__class__)
            is_owner = (
                obj.content_type_id == owner_ct.id
                and obj.object_id == owner.id
            )
            if not is_owner:
                raise NotFound("Moment not found.")

        # 1) Visibility gate (existing behavior)
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

        # 2) Analytics (safe)
        try:
            Moment.objects.filter(pk=obj.pk).update(
                view_count_internal=F("view_count_internal") + 1,
                last_viewed_at=timezone.now(),
            )
        except Exception:
            logger.exception("moment analytics update failed")

        serializer = self.get_serializer(obj)
        return Response(serializer.data)