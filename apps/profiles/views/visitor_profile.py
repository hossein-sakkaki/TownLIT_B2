# apps/profiles/views/visitor_profile.py

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.http import Http404

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.posts.models.moment import Moment
from apps.posts.models.pray import Prayer
from apps.posts.serializers.moments import MomentSerializer
from apps.posts.serializers.prayers import PrayerSerializer

from apps.core.pagination import ConfigurablePagination
from apps.core.visibility.constants import VISIBILITY_GLOBAL
from apps.core.visibility.query import VisibilityQuery

from apps.profiles.models.member import Member
from apps.profiles.models.guest import GuestUser
from apps.profiles.models.relationships import Friendship, Fellowship
from apps.profiles.serializers.member import (
    PublicMemberSerializer,
    LimitedMemberSerializer,
)
from apps.profiles.serializers.guest import (
    PublicGuestUserSerializer,
    LimitedGuestUserSerializer,
)
from apps.profiles.constants.fellowship import CONFIDANT
from apps.profiles.services.active_profile import get_active_profile

CustomUser = get_user_model()


# Visitor Profile ViewSet ---------------------------------------------------------------------------------------
class VisitorProfileViewSet(viewsets.GenericViewSet):
    """
    Public-facing profile with privacy gates.
    Supports both Member and GuestUser without breaking old Member endpoints.
    """
    permission_classes = [AllowAny]
    pagination_class = ConfigurablePagination
    pagination_page_size = 12

    # --- helpers -------------------------------------------------
    def _get_user(self, username: str):
        try:
            return (
                CustomUser.objects
                .filter(username=username)
                .filter(Q(is_deleted=False) | Q(is_deleted__isnull=True))
                .get()
            )
        except CustomUser.DoesNotExist:
            raise Http404

    def _get_member(self, username: str):
        try:
            return (
                Member.objects.select_related("user", "academic_record")
                .prefetch_related("service_types", "organization_memberships")
                .filter(
                    user__username=username,
                    is_active=True,
                )
                .filter(Q(user__is_deleted=False) | Q(user__is_deleted__isnull=True))
                .get()
            )
        except Member.DoesNotExist:
            raise Http404

    def _get_guest(self, username: str):
        try:
            return (
                GuestUser.objects.select_related("user")
                .filter(
                    user__username=username,
                    is_active=True,
                )
                .filter(Q(user__is_deleted=False) | Q(user__is_deleted__isnull=True))
                .get()
            )
        except GuestUser.DoesNotExist:
            raise Http404

    def _resolve_active_profile(self, username: str):
        """
        Resolve the active profile by username.
        Keeps old endpoints intact and powers unified visitor endpoints.
        """
        user = self._get_user(username)
        active = get_active_profile(user)

        if active.profile_type == "member":
            member = self._get_member(username)
            return {
                "profile_type": "member",
                "profile": member,
                "user": member.user,
            }

        if active.profile_type == "guest":
            guest = self._get_guest(username)
            return {
                "profile_type": "guest",
                "profile": guest,
                "user": guest.user,
            }

        raise Http404

    def _is_friend(self, viewer, owner_user) -> bool:
        # True if there's an accepted friendship in either direction
        if not viewer or not viewer.is_authenticated:
            return False

        return Friendship.objects.filter(
            Q(from_user=viewer, to_user=owner_user) |
            Q(from_user=owner_user, to_user=viewer),
            status="accepted",
            is_active=True,
        ).exists()

    def _is_confidant(self, viewer, member: Member) -> bool:
        """
        True iff the profile owner has designated the current viewer as a confidant.
        """
        if not viewer or not viewer.is_authenticated:
            return False

        owner = member.user
        return Fellowship.objects.filter(
            from_user=owner,
            to_user=viewer,
            fellowship_type=CONFIDANT,
            status__iexact="accepted",
        ).exists()

    # -------------------------------------------------------------
    # Visibility gate (Moments)
    # -------------------------------------------------------------
    def _visible_moments_qs(self, request, owner_profile):
        base = (
            Moment.objects
            .select_related("content_type")
            .order_by("-published_at", "-id")
        )

        # Apply visibility gate
        if not request.user or not request.user.is_authenticated:
            base = base.filter(visibility=VISIBILITY_GLOBAL)
        else:
            base = VisibilityQuery.for_viewer(
                viewer=request.user,
                base_queryset=base,
            )

        owner_ct = ContentType.objects.get_for_model(owner_profile.__class__)

        qs = base.filter(
            content_type_id=owner_ct.id,
            object_id=owner_profile.id,
        )

        # Hide not-yet-converted videos
        qs = qs.exclude(
            Q(video__isnull=False) & ~Q(is_converted=True)
        )

        return qs

    # -------------------------------------------------------------
    # Visibility gate (Prayers)
    # -------------------------------------------------------------
    def _visible_prayers_qs(self, request, member):
        base = (
            Prayer.objects
            .select_related("content_type")
            .order_by("-published_at", "-id")
        )

        # Apply visibility gate
        if not request.user or not request.user.is_authenticated:
            base = base.filter(visibility=VISIBILITY_GLOBAL)
        else:
            base = VisibilityQuery.for_viewer(
                viewer=request.user,
                base_queryset=base,
            )

        owner_ct = ContentType.objects.get_for_model(member.__class__)

        qs = base.filter(
            content_type_id=owner_ct.id,
            object_id=member.id,
        )

        # Hide not-yet-converted videos
        qs = qs.exclude(
            Q(video__isnull=False) & ~Q(is_converted=True)
        )

        return qs

    # --- response helper ----------------------------------------
    def _with_profile_gate(self, data, user, reason):
        """
        Attach profile_gate to a limited serializer response.
        """
        data["profile_gate"] = {
            "key": "profile_privacy_redirect",
            "reason": reason,
            "redirect_to": f"/lit/{user.username}",
        }
        return data

    # --- member gate --------------------------------------------
    def _member_profile_response(self, request, member: Member):
        user = member.user
        viewer = request.user if request.user.is_authenticated else None

        # Deleted -> 404
        if getattr(user, "is_deleted", False):
            return Response(
                {"error": "Member not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Suspended -> Limited
        if getattr(user, "is_suspended", False):
            data = LimitedMemberSerializer(member, context={"request": request}).data
            return Response(
                self._with_profile_gate(data, user, reason="account_suspended"),
                status=status.HTTP_200_OK,
            )

        # Paused -> Limited
        if getattr(user, "is_account_paused", False):
            data = LimitedMemberSerializer(member, context={"request": request}).data
            return Response(
                self._with_profile_gate(data, user, reason="account_paused"),
                status=status.HTTP_200_OK,
            )

        # Hidden by confidants
        if getattr(member, "is_hidden_by_confidants", False):
            if self._is_confidant(viewer, member):
                data = PublicMemberSerializer(member, context={"request": request}).data
                return Response(data, status=status.HTTP_200_OK)

            data = LimitedMemberSerializer(member, context={"request": request}).data
            return Response(
                self._with_profile_gate(data, user, reason="hidden_by_confidants"),
                status=status.HTTP_200_OK,
            )

        # Privacy enabled
        if getattr(member, "is_privacy", False):
            if self._is_friend(viewer, user):
                data = PublicMemberSerializer(member, context={"request": request}).data
                return Response(data, status=status.HTTP_200_OK)

            data = LimitedMemberSerializer(member, context={"request": request}).data
            return Response(
                self._with_profile_gate(data, user, reason="private_profile"),
                status=status.HTTP_200_OK,
            )

        # Default -> Public
        data = PublicMemberSerializer(member, context={"request": request}).data
        return Response(data, status=status.HTTP_200_OK)

    # --- guest gate ---------------------------------------------
    def _guest_profile_response(self, request, guest: GuestUser):
        user = guest.user
        viewer = request.user if request.user.is_authenticated else None

        # Deleted -> 404
        if getattr(user, "is_deleted", False):
            return Response(
                {"error": "Guest profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Suspended -> Limited
        if getattr(user, "is_suspended", False):
            data = LimitedGuestUserSerializer(guest, context={"request": request}).data
            return Response(
                self._with_profile_gate(data, user, reason="account_suspended"),
                status=status.HTTP_200_OK,
            )

        # Paused -> Limited
        if getattr(user, "is_account_paused", False):
            data = LimitedGuestUserSerializer(guest, context={"request": request}).data
            return Response(
                self._with_profile_gate(data, user, reason="account_paused"),
                status=status.HTTP_200_OK,
            )

        # Privacy enabled
        if getattr(guest, "is_privacy", False):
            if self._is_friend(viewer, user):
                data = PublicGuestUserSerializer(guest, context={"request": request}).data
                return Response(data, status=status.HTTP_200_OK)

            data = LimitedGuestUserSerializer(guest, context={"request": request}).data
            return Response(
                self._with_profile_gate(data, user, reason="private_profile"),
                status=status.HTTP_200_OK,
            )

        # Default -> Public
        data = PublicGuestUserSerializer(guest, context={"request": request}).data
        return Response(data, status=status.HTTP_200_OK)

    # Profile -----------------------------------------------------
    @action(detail=False, methods=["get"], url_path=r"profile/(?P<username>[^/]+)")
    def profile(self, request, username=None):
        """
        Old Member-only endpoint.
        Keeps current frontend behavior unchanged.
        """
        member = self._get_member(username)
        return self._member_profile_response(request, member)

    # Moments -----------------------------------------------------
    @action(detail=False, methods=["get"], url_path=r"profile/(?P<username>[^/]+)/moments")
    def moments(self, request, username=None):
        """
        Old Member-only moments endpoint.
        Keeps current frontend behavior unchanged.
        """
        member = self._get_member(username)
        qs = self._visible_moments_qs(request, member)

        page = self.paginate_queryset(qs)
        serializer = MomentSerializer(page, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data)

    # Prayers -----------------------------------------------------
    @action(detail=False, methods=["get"], url_path=r"profile/(?P<username>[^/]+)/prayers")
    def prayers(self, request, username=None):
        """
        Old Member-only prayers endpoint.
        Keeps current frontend behavior unchanged.
        """
        member = self._get_member(username)
        qs = self._visible_prayers_qs(request, member)

        page = self.paginate_queryset(qs)
        serializer = PrayerSerializer(page, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data)

    # Unified Profile --------------------------------------------
    @action(detail=False, methods=["get"], url_path=r"unified-profile/(?P<username>[^/]+)")
    def unified_profile(self, request, username=None):
        """
        Unified public profile for active Member or GuestUser.
        """
        resolved = self._resolve_active_profile(username)
        profile_type = resolved["profile_type"]
        profile = resolved["profile"]

        if profile_type == "member":
            return self._member_profile_response(request, profile)

        if profile_type == "guest":
            return self._guest_profile_response(request, profile)

        raise Http404

    # Unified Moments --------------------------------------------
    @action(detail=False, methods=["get"], url_path=r"unified-profile/(?P<username>[^/]+)/moments")
    def unified_moments(self, request, username=None):
        """
        Unified public moments for active Member or GuestUser.
        """
        resolved = self._resolve_active_profile(username)
        owner_profile = resolved["profile"]
        user = resolved["user"]

        # Deleted -> 404
        if getattr(user, "is_deleted", False):
            return Response(
                {"error": "Profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        qs = self._visible_moments_qs(request, owner_profile)

        page = self.paginate_queryset(qs)
        serializer = MomentSerializer(page, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data)