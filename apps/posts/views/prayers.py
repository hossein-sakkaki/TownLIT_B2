# apps/posts/views/prayers.py

import logging

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.db.models import F, Q
from django.db import transaction


from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError

from apps.posts.models.pray import Prayer, PrayerResponse, PrayerStatus
from apps.posts.serializers.prayers import PrayerSerializer, PrayerResponseSerializer

from apps.core.visibility.query import VisibilityQuery
from apps.core.visibility.policy import VisibilityPolicy
from apps.core.pagination import ConfigurablePagination, FeedCursorPagination

from apps.core.feed.trending import TrendingEngine
from apps.core.feed.hybrid import HybridFeedEngine
from apps.core.feed.personalized_trending import PersonalizedTrendingEngine

from apps.core.ownership.owner_gate_mixins import OwnerGateMixin
from apps.core.visibility.constants import VISIBILITY_GLOBAL


logger = logging.getLogger(__name__)


class PrayViewSet(OwnerGateMixin, viewsets.ModelViewSet):
    """
    Prayer API
    -------------------------
    - visibility-aware
    - owner-safe
    - response: one-to-one lifecycle
    - feed/trending: cursor-based
    - explore/me: page pagination
    """
    serializer_class = PrayerSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "slug"
    pagination_class = ConfigurablePagination
    pagination_page_size = 12

    # -------------------------------------------------------------------------
    # Permissions
    # -------------------------------------------------------------------------
    def get_permissions(self):
        """Public access only for safe read actions."""
        if self.action in ["retrieve", "explore", "trending"]:
            return [AllowAny()]
        return super().get_permissions()

    # -------------------------------------------------------------------------
    # Base queryset
    # -------------------------------------------------------------------------
    def get_queryset(self):
        base = (
            Prayer.objects
            .select_related("content_type")
            .select_related("response")  # one-to-one
            .order_by("-published_at", "-id")
        )

        if self.action == "retrieve":
            return base

        # Visibility filtering
        if not self.request.user or not self.request.user.is_authenticated:
            qs = base.filter(visibility=VISIBILITY_GLOBAL)
        else:
            qs = VisibilityQuery.for_viewer(
                viewer=self.request.user,
                base_queryset=base,
            )

        # Visitor: hide unconverted prayer videos
        if not self.request.user.is_authenticated:
            qs = qs.exclude(Q(video__isnull=False) & ~Q(is_converted=True))

        return qs

    # -------------------------------------------------------------------------
    # Owner resolution
    # -------------------------------------------------------------------------
    def _get_request_owner(self):
        user = self.request.user
        if hasattr(user, "member_profile"):
            return user.member_profile
        if hasattr(user, "guest_profile"):
            return user.guest_profile
        return None

    def _assert_is_owner(self, obj: Prayer):
        owner = self._get_request_owner()
        if not owner:
            raise PermissionDenied("Invalid owner context.")

        owner_ct = ContentType.objects.get_for_model(owner.__class__)
        if obj.content_type_id != owner_ct.id or obj.object_id != owner.id:
            raise PermissionDenied("You do not own this Prayer.")

    # -------------------------------------------------------------------------
    # Create / Update / Delete
    # -------------------------------------------------------------------------
    def perform_create(self, serializer):
        owner = self._get_request_owner()
        if not owner:
            raise PermissionDenied("Only members or guest users can create prayers.")

        serializer.save(
            content_type=ContentType.objects.get_for_model(owner.__class__),
            object_id=owner.id,
        )

    def perform_update(self, serializer):
        obj = self.get_object()
        self._assert_is_owner(obj)
        serializer.save(updated_at=timezone.now())

    def perform_destroy(self, instance):
        """Hard delete cascade (response/comments/reactions/media...)."""
        self._assert_is_owner(instance)
        instance.delete()

    # -------------------------------------------------------------------------
    # Feed (cursor-based)
    # -------------------------------------------------------------------------
    @action(detail=False, methods=["get"], pagination_class=FeedCursorPagination)
    def feed(self, request):
        qs = HybridFeedEngine.apply(self.get_queryset(), viewer=request.user)
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    # -------------------------------------------------------------------------
    # Trending for me (cursor-based)
    # -------------------------------------------------------------------------
    @action(detail=False, methods=["get"], pagination_class=FeedCursorPagination)
    def trending_for_me(self, request):
        qs = PersonalizedTrendingEngine.apply(self.get_queryset(), viewer=request.user)
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    # -------------------------------------------------------------------------
    # Trending (public)
    # -------------------------------------------------------------------------
    @action(
        detail=False,
        methods=["get"],
        pagination_class=FeedCursorPagination,
        permission_classes=[AllowAny],
    )
    def trending(self, request):
        qs = TrendingEngine.apply(self.get_queryset(), window_seconds=24 * 60 * 60)
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    # -------------------------------------------------------------------------
    # My prayers (owner only)
    # -------------------------------------------------------------------------
    @action(detail=False, methods=["get"])
    def me(self, request):
        owner = self._get_request_owner()
        if not owner:
            raise PermissionDenied("Invalid owner type.")

        owner_ct = ContentType.objects.get_for_model(owner.__class__)
        qs = self.get_queryset().filter(content_type_id=owner_ct.id, object_id=owner.id)

        try:
            page = self.paginate_queryset(qs)
        except NotFound:
            return Response({"count": qs.count(), "next": None, "previous": None, "results": []})

        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    # -------------------------------------------------------------------------
    # Explore (public discover)
    # -------------------------------------------------------------------------
    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def explore(self, request):
        qs = self.get_queryset().filter(visibility=VISIBILITY_GLOBAL)
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    # -------------------------------------------------------------------------
    # Retrieve (public-safe, analytics)
    # -------------------------------------------------------------------------
    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()

        # Owner hard gate (existing mixin behavior)
        self.apply_hard_owner_gate(request, obj)

        # Hard domain: unconverted video only owner (404 for others)
        if obj.video and obj.is_converted is not True:
            owner = self._get_request_owner() if request.user.is_authenticated else None
            if not owner:
                raise NotFound("Prayer not found.")

            owner_ct = ContentType.objects.get_for_model(owner.__class__)
            is_owner = obj.content_type_id == owner_ct.id and obj.object_id == owner.id
            if not is_owner:
                raise NotFound("Prayer not found.")

        # Visibility gate
        reason = VisibilityPolicy.gate_reason(viewer=request.user, obj=obj)
        if reason is not None:
            return Response(
                {"detail": "Access restricted.", "code": reason, "content_type": "prayer", "slug": obj.slug},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Analytics
        try:
            Prayer.objects.filter(pk=obj.pk).update(
                view_count_internal=F("view_count_internal") + 1,
                last_viewed_at=timezone.now(),
            )
        except Exception:
            logger.exception("prayer analytics update failed")

        serializer = self.get_serializer(obj)
        return Response(serializer.data)

    # -------------------------------------------------------------------------
    # Respond (create/update response)
    # -------------------------------------------------------------------------
    @action(detail=True, methods=["post", "patch"], permission_classes=[IsAuthenticated])
    def respond(self, request, slug=None):
        """
        Create or update PrayerResponse.
        Entire lifecycle runs inside one transaction.
        Media conversion triggers AFTER commit.
        """
        prayer: Prayer = self.get_object()
        self._assert_is_owner(prayer)

        with transaction.atomic():  # <-- single transaction boundary

            existing = getattr(prayer, "response", None)

            result_status = request.data.get("result_status")
            if result_status not in (PrayerStatus.ANSWERED, PrayerStatus.NOT_ANSWERED):
                raise ValidationError({"result_status": "Must be 'answered' or 'not_answered'."})

            if existing is None:
                serializer = PrayerResponseSerializer(
                    data=request.data,
                    context={"request": request}
                )
                serializer.is_valid(raise_exception=True)

                response_obj = serializer.save(prayer=prayer)

                return Response(
                    PrayerResponseSerializer(response_obj, context={"request": request}).data,
                    status=201
                )

            serializer = PrayerResponseSerializer(
                existing,
                data=request.data,
                partial=(request.method == "PATCH"),
                context={"request": request},
            )
            serializer.is_valid(raise_exception=True)

            response_obj = serializer.save(updated_at=timezone.now())

            return Response(
                PrayerResponseSerializer(response_obj, context={"request": request}).data,
                status=200
            )

    # -------------------------------------------------------------------------
    # Delete response (optional endpoint)
    # -------------------------------------------------------------------------
    @action(detail=True, methods=["delete"], permission_classes=[IsAuthenticated])
    def delete_response(self, request, slug=None):
        """Delete response and reset prayer to WAITING."""
        prayer: Prayer = self.get_object()
        self._assert_is_owner(prayer)

        existing = getattr(prayer, "response", None)
        if not existing:
            return Response(status=204)

        existing.delete()
        return Response(status=204)