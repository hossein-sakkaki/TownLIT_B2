# apps/posts/views/moments.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-14.
# Last Update by Hossein Sakkaki on 2026-08-14.

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.db.models import F, Q
from django.db import transaction

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework import status

from apps.posts.models.moment import Moment
from apps.posts.serializers.moments import (
    MomentProfileGridSerializer,
    MomentSerializer,
)
from apps.posts.services.moment_content_safety import (
    enforce_moment_content_safety,
)
from apps.posts.services.moment_media_content_safety import (
    enforce_moment_media_content_safety,
)
from apps.content_safety.view_mixins import (
    ContentSafetyJobResponseMixin,
)

from apps.core.visibility.query import VisibilityQuery
from apps.core.visibility.policy import VisibilityPolicy
from apps.core.pagination import ConfigurablePagination, FeedCursorPagination

from apps.core.feed.trending import TrendingEngine
from apps.core.feed.hybrid import HybridFeedEngine
from apps.core.feed.personalized_trending import PersonalizedTrendingEngine
from apps.core.ownership.owner_gate_mixins import OwnerGateMixin
from apps.core.ownership.utils import resolve_owner_from_request
from apps.core.visibility.constants import VISIBILITY_GLOBAL
from apps.core.boundaries.query import BoundaryVisibilityQuery
from apps.sanctuary.services.held_content_access import (
    exclude_active_safety_held_targets,
)

import logging

logger = logging.getLogger(__name__)

MOMENT_PAGE_SIZE = 21


class MomentViewSet(
    ContentSafetyJobResponseMixin,
    OwnerGateMixin,
    viewsets.ModelViewSet,
):
    """
    Moment API
    -------------------------
    - visibility-aware
    - owner-safe
    - Content Safety protected for captions, images, thumbnails, and videos
    - supports legacy single image/video Moments
    - supports JSON-backed multi-photo Moments
    - feed: cursor-based pagination
    - explore / me: page-number pagination
    """

    serializer_class = MomentSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "slug"
    pagination_class = ConfigurablePagination
    pagination_page_size = MOMENT_PAGE_SIZE

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
    def get_queryset(
        self,
    ):
        base = (
            Moment.objects
            .select_related(
                "content_type"
            )
            .order_by(
                "-published_at",
                "-id",
            )
        )

        # Owner mutation/detail actions must be able to reach the target even
        # while Content Safety or Media Conversion is incomplete.
        #
        # Authorization is enforced later by the action-specific owner gates.
        if self.action in {
            "retrieve",
            "update",
            "partial_update",
            "destroy",
        }:
            return base

        if (
            not self.request.user
            or not self.request.user.is_authenticated
        ):
            qs = base.filter(
                visibility=VISIBILITY_GLOBAL
            )

        else:
            qs = VisibilityQuery.for_viewer(
                viewer=self.request.user,
                base_queryset=base,
            )

            qs = (
                BoundaryVisibilityQuery
                .exclude_boundary_conflicts(
                    qs,
                    viewer=self.request.user,
                )
            )

        qs = exclude_active_safety_held_targets(
            qs,
            target_model=Moment,
            viewer=self.request.user,
        )

        # A raw/unconverted video is pre-publication media.
        #
        # It must never enter list/feed/explore/trending results, regardless
        # of whether the viewer is authenticated.
        qs = qs.exclude(
            Q(is_converted=False)
            & Q(video__isnull=False)
            & ~Q(video="")
        )

        return qs

    # -------------------------------------------------
    # Owner resolution
    # -------------------------------------------------
    def _get_request_owner(self):
        """
        Resolve active owner profile from request.
        """
        return resolve_owner_from_request(self.request)

    def _assert_is_owner(self, obj):
        """
        Ensure the active owner owns this Moment.
        """
        owner = self._get_request_owner()

        if not owner:
            raise PermissionDenied(
                "Invalid owner context."
            )

        owner_ct = ContentType.objects.get_for_model(
            owner.__class__
        )

        if (
            obj.content_type_id != owner_ct.id
            or obj.object_id != owner.id
        ):
            raise PermissionDenied(
                "You do not own this Moment."
            )

    # -------------------------------------------------
    # Create
    # -------------------------------------------------
    def perform_create(
        self,
        serializer,
    ):
        """
        Attach the active owner and schedule configured asynchronous
        Content Safety jobs.

        Safety order:
        1. caption safety
        2. synchronous image/thumbnail safety
        3. persist raw media privately
        4. schedule configured async media safety
        5. approved raw video is handed to Media Conversion later
        """

        owner = self._get_request_owner()

        if not owner:
            raise PermissionDenied(
                "Only members or guest users can create moments."
            )

        submitted_data = dict(
            serializer.validated_data
        )

        # Cheap text gate first.
        enforce_moment_content_safety(
            validated_data=(
                serializer.validated_data
            ),
            actor=self.request.user,
        )

        # Important:
        # This service must inspect synchronous assets only.
        #
        # - uploaded photos: synchronous
        # - video thumbnail: synchronous
        # - raw video: asynchronous through ContentSafetyJob
        enforce_moment_media_content_safety(
            validated_data=(
                serializer.validated_data
            ),
            request=self.request,
            actor=self.request.user,
        )

        owner_ct = (
            ContentType.objects
            .get_for_model(
                owner.__class__
            )
        )

        with transaction.atomic():
            instance = serializer.save(
                content_type=owner_ct,
                object_id=owner.id,
            )

            self.schedule_content_safety_jobs(
                instance=instance,
                submitted_data=submitted_data,
            )
        
    # -------------------------------------------------
    # Update
    # -------------------------------------------------
    def perform_update(
        self,
        serializer,
    ):
        """
        Owner-safe Moment update.

        Current Moment policy does not permit photo/video replacement.
        The shared async Safety scheduling hook remains in place so future
        editable safety-gated fields do not require another ViewSet design.
        """

        obj = self.get_object()

        self._assert_is_owner(
            obj
        )

        submitted_data = dict(
            serializer.validated_data
        )

        enforce_moment_content_safety(
            validated_data=(
                serializer.validated_data
            ),
            actor=self.request.user,
            instance=obj,
        )

        enforce_moment_media_content_safety(
            validated_data=(
                serializer.validated_data
            ),
            request=self.request,
            actor=self.request.user,
        )

        with transaction.atomic():
            instance = serializer.save(
                updated_at=timezone.now()
            )

            self.schedule_content_safety_jobs(
                instance=instance,
                submitted_data=submitted_data,
            )
        
    # -------------------------------------------------
    # Delete
    # -------------------------------------------------
    def perform_destroy(self, instance):
        """
        Owner-safe delete.
        Cleanup signal removes media files.
        """
        self._assert_is_owner(
            instance
        )

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

        page = self.paginate_queryset(
            qs
        )

        serializer = self.get_serializer(
            page,
            many=True
        )

        return self.get_paginated_response(
            serializer.data
        )

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

        page = self.paginate_queryset(
            qs
        )

        serializer = self.get_serializer(
            page,
            many=True
        )

        return self.get_paginated_response(
            serializer.data
        )

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

        page = self.paginate_queryset(
            qs
        )

        serializer = self.get_serializer(
            page,
            many=True
        )

        return self.get_paginated_response(
            serializer.data
        )

    # -------------------------------------------------
    # My moments
    # -------------------------------------------------
    @action(
        detail=False,
        methods=["get"],
    )
    def me(self, request):
        owner = self._get_request_owner()

        if not owner:
            raise PermissionDenied(
                "Invalid owner type."
            )

        owner_ct = ContentType.objects.get_for_model(
            owner.__class__
        )

        qs = (
            Moment.objects
            .filter(
                content_type_id=owner_ct.id,
                object_id=owner.id,
            )
            .only(
                "id",
                "slug",

                # Content
                "caption",

                # Legacy media fields
                "image",
                "video",
                "thumbnail",

                "media_assets",

                # Multi-photo metadata
                "media_kind",
                "image_items",
                "cover_image_id",
                "audio_payload",

                # Visibility / UI
                "visibility",
                "is_hidden",

                # Pipeline / timestamps
                "is_converted",
                "published_at",
                "updated_at",

                # Ownership
                "content_type_id",
                "object_id",
            )
            .order_by(
                "-published_at",
                "-id"
            )
        )

        qs = exclude_active_safety_held_targets(
            qs,
            target_model=Moment,
            viewer=request.user,
        )
         
        try:
            page = self.paginate_queryset(
                qs
            )
        except NotFound:
            return Response(
                {
                    "count": qs.count(),
                    "next": None,
                    "previous": None,
                    "results": [],
                }
            )

        serializer = MomentProfileGridSerializer(
            page,
            many=True,
            context={
                "request": request,
            },
        )

        return self.get_paginated_response(
            serializer.data
        )

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
            .filter(
                visibility=VISIBILITY_GLOBAL
            )
        )

        page = self.paginate_queryset(
            qs
        )

        serializer = self.get_serializer(
            page,
            many=True
        )

        return self.get_paginated_response(
            serializer.data
        )

    # -------------------------------------------------
    # Retrieve
    # -------------------------------------------------
    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()

        # Hard owner-level gate.
        self.apply_hard_owner_gate(
            request,
            obj
        )

        # Not-yet-converted video is owner-only.
        if obj.video and obj.is_converted is not True:
            owner = (
                resolve_owner_from_request(
                    request
                )
                if request.user.is_authenticated
                else None
            )

            if not owner:
                raise NotFound(
                    "Moment not found."
                )

            owner_ct = ContentType.objects.get_for_model(
                owner.__class__
            )

            is_owner = (
                obj.content_type_id == owner_ct.id
                and obj.object_id == owner.id
            )

            if not is_owner:
                raise NotFound(
                    "Moment not found."
                )

        # Visibility gate.
        reason = VisibilityPolicy.gate_reason(
            viewer=request.user,
            obj=obj,
        )

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

        # Analytics.
        try:
            Moment.objects.filter(
                pk=obj.pk
            ).update(
                view_count_internal=F(
                    "view_count_internal"
                ) + 1,
                last_viewed_at=timezone.now(),
            )
        except Exception:
            logger.exception(
                "moment analytics update failed"
            )

        serializer = self.get_serializer(
            obj
        )

        return Response(
            serializer.data
        )