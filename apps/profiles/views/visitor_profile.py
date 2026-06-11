# apps/profiles/views/visitor_profile.py

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.db.models.functions import Lower
from django.http import Http404

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.posts.models.moment import Moment
from apps.posts.models.pray import Prayer
from apps.posts.serializers.moments import MomentSerializer, MomentProfileGridSerializer
from apps.posts.serializers.prayers import PrayerSerializer, PrayerProfileGridSerializer

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
from apps.accounts.serializers.user_serializers import SimpleCustomUserSerializer
from apps.core.boundaries.services.policy import BoundaryPolicy

CustomUser = get_user_model()
SAFE_PROFILE_UNAVAILABLE_REASON = "temporarily_unavailable"

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
    # Boundary helpers
    # -------------------------------------------------------------
    def _has_boundary_between(self, viewer, owner_user) -> bool:
        """
        Return True when an active Boundary exists in either direction
        between viewer and profile owner.

        Stillness intentionally does NOT affect profile visibility.
        """
        if not viewer or not getattr(viewer, "is_authenticated", False):
            return False

        if not owner_user:
            return False

        if getattr(viewer, "id", None) == getattr(owner_user, "id", None):
            return False

        try:
            return BoundaryPolicy.has_boundary_between(viewer, owner_user)
        except Exception:
            return False

    def _filter_user_ids_for_boundary(self, viewer, user_ids: set[int]) -> set[int]:
        """
        Remove users from a visible user-id set when Boundary exists
        between viewer and that user.

        Used for profile friends/mutual friends output.
        """
        if not viewer or not getattr(viewer, "is_authenticated", False):
            return user_ids

        if not user_ids:
            return set()

        visible_ids = set()

        users = (
            CustomUser.objects
            .filter(id__in=user_ids)
            .only("id")
        )

        for user in users:
            if not self._has_boundary_between(viewer, user):
                visible_ids.add(user.id)

        return visible_ids
    
    # -------------------------------------------------------------
    # Visibility gate (Moments)
    # -------------------------------------------------------------
    def _visible_moments_qs(self, request, owner_profile):
        base = (
            Moment.objects
            .select_related("content_type")
            .order_by("-published_at", "-id")
        )

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

        qs = qs.exclude(
            Q(video__isnull=False) &
            ~Q(video="") &
            ~Q(is_converted=True)
        )

        return qs

    # -------------------------------------------------------------
    # Visibility gate (Prayers)
    # -------------------------------------------------------------
    def _visible_prayers_qs(self, request, member):
        base = (
            Prayer.objects
            .select_related("content_type", "response")
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

        # Hide not-yet-converted main prayer videos from visitor/public grid.
        qs = qs.exclude(
            Q(video__isnull=False) &
            ~Q(video="") &
            ~Q(is_converted=True)
        )

        # Hide prayers whose response video is still converting.
        # This prevents leaking conversion/job payloads or half-ready response cards.
        qs = qs.exclude(
            Q(response__video__isnull=False) &
            ~Q(response__video="") &
            ~Q(response__is_converted=True)
        )

        return qs

    # --- response helper ----------------------------------------
    def _with_profile_gate(self, data, user, reason):
        """
        Attach profile_gate to a limited serializer response.

        Public reasons must never expose safety internals.
        """
        safe_reason = (
            SAFE_PROFILE_UNAVAILABLE_REASON
            if reason == "hidden_by_confidants"
            else reason
        )

        data["profile_gate"] = {
            "key": "profile_privacy_redirect",
            "reason": safe_reason,
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

        # Boundary -> Limited profile in both directions
        if self._has_boundary_between(viewer, user):
            data = LimitedMemberSerializer(member, context={"request": request}).data
            return Response(
                self._with_profile_gate(data, user, reason="boundary"),
                status=status.HTTP_200_OK,
            )
            
        # Hidden by safety gate.
        # This must apply before the owner full-profile shortcut.
        # Never expose internal confidant/safety reason to the client.
        if getattr(member, "is_hidden_by_confidants", False):
            if self._is_confidant(viewer, member):
                data = PublicMemberSerializer(member, context={"request": request}).data
                return Response(data, status=status.HTTP_200_OK)

            data = LimitedMemberSerializer(member, context={"request": request}).data
            return Response(
                self._with_profile_gate(
                    data,
                    user,
                    reason=SAFE_PROFILE_UNAVAILABLE_REASON,
                ),
                status=status.HTTP_200_OK,
            )

        # Owner can view own profile only when no safety gate is active.
        if viewer and viewer.is_authenticated and viewer.id == user.id:
            data = PublicMemberSerializer(member, context={"request": request}).data
            return Response(data, status=status.HTTP_200_OK)
        
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

        # Owner can always view own guest profile
        if viewer and viewer.is_authenticated and viewer.id == user.id:
            data = PublicGuestUserSerializer(guest, context={"request": request}).data
            return Response(data, status=status.HTTP_200_OK)

        # Boundary -> Limited profile in both directions
        if self._has_boundary_between(viewer, user):
            data = LimitedGuestUserSerializer(guest, context={"request": request}).data
            return Response(
                self._with_profile_gate(data, user, reason="boundary"),
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

    # --- content gate -------------------------------------------
    def _profile_content_gate_response(self, request, profile, user, profile_type):
        """
        Content-level gate for visitor profile content endpoints.

        If the profile itself is limited/private/hidden/suspended/paused,
        content endpoints must not leak profile content.
        """

        viewer = request.user if request.user.is_authenticated else None

        # Deleted -> 404
        if getattr(user, "is_deleted", False):
            return Response(
                {"detail": "Profile not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Suspended
        if getattr(user, "is_suspended", False):
            return Response(
                self._empty_paginated_gate_payload(user, "account_suspended"),
                status=status.HTTP_200_OK,
            )

        # Paused
        if getattr(user, "is_account_paused", False):
            return Response(
                self._empty_paginated_gate_payload(user, "account_paused"),
                status=status.HTTP_200_OK,
            )

        # Boundary -> hide profile content in both directions
        if self._has_boundary_between(viewer, user):
            return Response(
                self._empty_paginated_gate_payload(user, "boundary"),
                status=status.HTTP_200_OK,
            )
            
        # Member-only safety gate.
        if profile_type == "member" and getattr(profile, "is_hidden_by_confidants", False):
            if self._is_confidant(viewer, profile):
                return None

            return Response(
                self._empty_paginated_gate_payload(
                    user,
                    SAFE_PROFILE_UNAVAILABLE_REASON,
                ),
                status=status.HTTP_200_OK,
            )

        # Owner can always view own public/profile content route
        if viewer and viewer.is_authenticated and viewer.id == user.id:
            return None
        
        # Privacy
        if getattr(profile, "is_privacy", False):
            if self._is_friend(viewer, user):
                return None

            return Response(
                self._empty_paginated_gate_payload(user, "private_profile"),
                status=status.HTTP_200_OK,
            )

        return None

    # --- empty gate payload helper --------------------------------
    def _empty_paginated_gate_payload(self, user, reason):
        """
        Return a pagination-compatible empty response with profile_gate.

        This keeps iOS PaginatedResponseDTO decoding safe even when the
        content endpoint is blocked by profile-level privacy/security gates.
        """
        return {
            "count": 0,
            "next": None,
            "previous": None,
            "results": [],
            "profile_gate": {
                "key": "profile_privacy_redirect",
                "reason": reason,
                "redirect_to": f"/lit/{user.username}",
            },
        }


    # -------------------------------------------------------------
    # Friends helpers
    # -------------------------------------------------------------
    def _accepted_friend_edges_for_user(self, user):
        return (
            Friendship.objects
            .filter(
                Q(from_user=user) | Q(to_user=user),
                status="accepted",
                is_active=True,
            )
            .filter(from_user__is_deleted=False, to_user__is_deleted=False)
            .values("id", "from_user_id", "to_user_id")
        )

    def _friend_ids_for_user(self, user):
        if not user or not getattr(user, "is_authenticated", False):
            return set()

        uid = user.id
        friend_ids = set()

        for edge in self._accepted_friend_edges_for_user(user):
            friend_ids.add(
                edge["to_user_id"]
                if edge["from_user_id"] == uid
                else edge["from_user_id"]
            )

        return friend_ids

    def _friendship_ids_map_for_viewer(self, viewer):
        """
        Map friend_user_id -> friendship_row_id for the authenticated viewer.
        Useful for frontend compatibility if the row serializer exposes friendship_id.
        """
        if not viewer or not getattr(viewer, "is_authenticated", False):
            return {}

        uid = viewer.id
        output = {}

        for edge in self._accepted_friend_edges_for_user(viewer):
            counterpart_id = (
                edge["to_user_id"]
                if edge["from_user_id"] == uid
                else edge["from_user_id"]
            )
            output[counterpart_id] = edge["id"]

        return output

    def _empty_friends_gate_payload(self, user, reason):
        return {
            "total_count": 0,
            "mutual_count": 0,
            "mutual_friends": [],
            "other_friends": [],
            "profile_gate": {
                "key": "profile_privacy_redirect",
                "reason": reason,
                "redirect_to": f"/lit/{user.username}",
            },
        }

    def _profile_friends_gate_response(self, request, profile, user, profile_type):
        """
        Same profile-level gate logic as content endpoints,
        but returns a friends-list-compatible payload.
        """
        viewer = request.user if request.user.is_authenticated else None

        # Owner can always view own friend list through visitor route.
        if viewer and viewer.is_authenticated and viewer.id == user.id:
            return None

        if getattr(user, "is_deleted", False):
            return Response(
                {"detail": "Profile not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if getattr(user, "is_suspended", False):
            return Response(
                self._empty_friends_gate_payload(user, "account_suspended"),
                status=status.HTTP_200_OK,
            )

        if getattr(user, "is_account_paused", False):
            return Response(
                self._empty_friends_gate_payload(user, "account_paused"),
                status=status.HTTP_200_OK,
            )
            
        # Boundary -> hide profile friends list in both directions
        if self._has_boundary_between(viewer, user):
            return Response(
                self._empty_friends_gate_payload(user, "boundary"),
                status=status.HTTP_200_OK,
            )
            
        if profile_type == "member" and getattr(profile, "is_hidden_by_confidants", False):
            if self._is_confidant(viewer, profile):
                return None

            return Response(
                self._empty_friends_gate_payload(
                    user,
                    SAFE_PROFILE_UNAVAILABLE_REASON,
                ),
                status=status.HTTP_200_OK,
            )

        if getattr(profile, "is_privacy", False):
            if self._is_friend(viewer, user):
                return None

            return Response(
                self._empty_friends_gate_payload(user, "private_profile"),
                status=status.HTTP_200_OK,
            )

        return None

    def _serialize_friend_users(self, request, users_qs):
        viewer = request.user if request.user.is_authenticated else None

        viewer_friend_ids = self._friend_ids_for_user(viewer)
        friendship_ids_map = self._friendship_ids_map_for_viewer(viewer)

        serializer = SimpleCustomUserSerializer(
            users_qs,
            many=True,
            context={
                "request": request,
                "friend_ids": viewer_friend_ids,
                "friendship_ids": friendship_ids_map,
                "sent_request_map": {},
                "received_request_map": {},
                "fellowship_ids": {},
            },
        )

        return serializer.data
    
    
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
        member = self._get_member(username)

        gate_response = self._profile_content_gate_response(
            request=request,
            profile=member,
            user=member.user,
            profile_type="member",
        )

        if gate_response is not None:
            return gate_response

        qs = self._visible_moments_qs(request, member)

        page = self.paginate_queryset(qs)
        serializer = MomentSerializer(page, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data)

    # Prayers -----------------------------------------------------
    @action(detail=False, methods=["get"], url_path=r"profile/(?P<username>[^/]+)/prayers")
    def prayers(self, request, username=None):
        """
        Old Member-only prayers endpoint.
        Keeps current frontend behavior unchanged,
        but applies profile-level privacy/security gates before exposing content.
        """
        member = self._get_member(username)

        gate_response = self._profile_content_gate_response(
            request=request,
            profile=member,
            user=member.user,
            profile_type="member",
        )

        if gate_response is not None:
            return gate_response

        qs = self._visible_prayers_qs(request, member)

        page = self.paginate_queryset(qs)
        serializer = PrayerSerializer(
            page,
            many=True,
            context={"request": request},
        )

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
        profile_type = resolved["profile_type"]
        owner_profile = resolved["profile"]
        user = resolved["user"]

        gate_response = self._profile_content_gate_response(
            request=request,
            profile=owner_profile,
            user=user,
            profile_type=profile_type,
        )

        if gate_response is not None:
            return gate_response

        qs = self._visible_moments_qs(request, owner_profile)

        page = self.paginate_queryset(qs)
        serializer = MomentProfileGridSerializer(
            page,
            many=True,
            context={"request": request},
        )
        return self.get_paginated_response(serializer.data)
    
    # Unified Prayers --------------------------------------------
    @action(detail=False, methods=["get"], url_path=r"unified-profile/(?P<username>[^/]+)/prayers")
    def unified_prayers(self, request, username=None):
        """
        Unified public prayers for active profile.

        Member can have prayers.
        Guest currently has no prayers, but profile-level gates are still applied
        so iOS can understand limited/private guest state consistently.
        """
        resolved = self._resolve_active_profile(username)
        profile_type = resolved["profile_type"]
        owner_profile = resolved["profile"]
        user = resolved["user"]

        gate_response = self._profile_content_gate_response(
            request=request,
            profile=owner_profile,
            user=user,
            profile_type=profile_type,
        )

        if gate_response is not None:
            return gate_response

        # Guest has no prayers for now.
        if profile_type != "member":
            return Response(
                {
                    "count": 0,
                    "next": None,
                    "previous": None,
                    "results": [],
                },
                status=status.HTTP_200_OK,
            )

        qs = self._visible_prayers_qs(request, owner_profile)

        page = self.paginate_queryset(qs)
        serializer = PrayerProfileGridSerializer(
            page,
            many=True,
            context={"request": request},
        )
        return self.get_paginated_response(serializer.data)
    
    # Unified Friends ---------------------------------------------
    @action(detail=False, methods=["get"], url_path=r"unified-profile/(?P<username>[^/]+)/friends")
    def unified_friends(self, request, username=None):
        """
        Unified public friends list for active Member or GuestUser.

        Returns friends split into:
        - mutual_friends: friends shared between viewer and profile owner
        - other_friends: remaining visible friends of the profile owner
        """
        resolved = self._resolve_active_profile(username)
        profile_type = resolved["profile_type"]
        owner_profile = resolved["profile"]
        owner_user = resolved["user"]

        gate_response = self._profile_friends_gate_response(
            request=request,
            profile=owner_profile,
            user=owner_user,
            profile_type=profile_type,
        )

        if gate_response is not None:
            return gate_response

        owner_friend_ids = self._friend_ids_for_user(owner_user)

        viewer = request.user if request.user.is_authenticated else None
        viewer_friend_ids = self._friend_ids_for_user(viewer)

        # Boundary-aware friend visibility:
        # Do not expose users inside another profile's friends list
        # if viewer has Boundary with those users in either direction.
        owner_friend_ids = self._filter_user_ids_for_boundary(
            viewer,
            owner_friend_ids,
        )

        viewer_friend_ids = self._filter_user_ids_for_boundary(
            viewer,
            viewer_friend_ids,
        )

        mutual_ids = owner_friend_ids.intersection(viewer_friend_ids)
        other_ids = owner_friend_ids.difference(mutual_ids)

        base_qs = (
            CustomUser.objects
            .filter(
                id__in=owner_friend_ids,
                is_active=True,
                is_deleted=False,
            )
            .select_related("label", "member_profile")
            .annotate(username_lower=Lower("username"))
        )

        mutual_qs = (
            base_qs
            .filter(id__in=mutual_ids)
            .order_by("username_lower")
        )

        other_qs = (
            base_qs
            .filter(id__in=other_ids)
            .order_by("username_lower")
        )

        return Response(
            {
                "total_count": len(owner_friend_ids),
                "mutual_count": len(mutual_ids),
                "mutual_friends": self._serialize_friend_users(request, mutual_qs),
                "other_friends": self._serialize_friend_users(request, other_qs),
                "profile_gate": None,
            },
            status=status.HTTP_200_OK,
        )