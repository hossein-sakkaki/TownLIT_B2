# apps/profiles/views/guest.py

from django.contrib.auth import get_user_model

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.profiles.models.guest import GuestUser
from apps.profiles.serializers.guest import (
    GuestUserSerializer,
    PublicGuestUserSerializer,
    LimitedGuestUserSerializer,
)
from apps.accounts.serializers.user_serializers import CustomUserSerializer
from apps.posts.models.moment import Moment
from apps.posts.serializers.moments import MomentSerializer
from apps.posts.services.feed_access import get_visible_posts

CustomUser = get_user_model()


class GuestUserViewSet(viewsets.ModelViewSet):
    queryset = GuestUser.objects.all()
    permission_classes = [IsAuthenticated]
    serializer_class = GuestUserSerializer

    def get_queryset(self):
        # Stop deleted users at query level
        if getattr(self.request.user, "is_deleted", False):
            return GuestUser.objects.none()
        return GuestUser.objects.filter(is_active=True, user=self.request.user)

    def list(self, request, *args, **kwargs):
        raise MethodNotAllowed("GET")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def retrieve(self, request, *args, **kwargs):
        # Self profile only
        if getattr(request.user, "is_deleted", False):
            return Response(
                {"error": "Your account is deactivated. Reactivate first to access your profile."},
                status=status.HTTP_403_FORBIDDEN,
            )

        guest = self.get_object()

        if guest.user_id != request.user.id:
            raise PermissionDenied("You can only access your own profile here.")

        if guest.user.is_suspended:
            return Response(
                {"error": "Your profile is suspended and cannot be accessed by you."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(guest)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="my-profile", permission_classes=[IsAuthenticated])
    def my_profile(self, request):
        # Block deleted accounts
        if getattr(request.user, "is_deleted", False):
            return Response(
                {"error": "Your account is deactivated. Reactivate first to access your profile."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            guest = request.user.guest_profile
        except (GuestUser.DoesNotExist, AttributeError):
            return Response(
                {"error": "Guest profile not found. Please complete your profile registration."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not guest.is_active:
            return Response(
                {"error": "Your guest profile is inactive."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if guest.user.is_suspended:
            return Response(
                {"error": "Your profile is suspended and cannot be accessed by you."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(guest)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="update-profile", permission_classes=[IsAuthenticated])
    def update_profile(self, request):
        # Block deleted accounts
        if getattr(request.user, "is_deleted", False):
            return Response(
                {"error": "Your account is deactivated. Reactivate first to update your profile."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            guest = request.user.guest_profile
        except (GuestUser.DoesNotExist, AttributeError):
            return Response(
                {"error": "Guest profile not found. Please create a guest profile first."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = self.get_serializer(guest, data=request.data, partial=True)

        if not serializer.is_valid():
            return Response(
                {
                    "error": "Invalid data. Please check the provided fields.",
                    "details": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated_guest = serializer.save()

        user_data = CustomUserSerializer(
            updated_guest.user,
            context={"request": request},
        ).data

        guest_data = GuestUserSerializer(
            updated_guest,
            context={"request": request},
        ).data

        return Response(
            {
                "message": "Guest profile updated successfully.",
                "guest": guest_data,
                "user": user_data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="update-profile-image", permission_classes=[IsAuthenticated])
    def update_profile_image(self, request):
        # Block deleted accounts
        if getattr(request.user, "is_deleted", False):
            return Response(
                {"error": "Your account is deactivated. Reactivate first to change your profile image."},
                status=status.HTTP_403_FORBIDDEN,
            )

        profile_image = request.FILES.get("profile_image")
        if not profile_image:
            return Response(
                {"error": "No profile image uploaded."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            guest = request.user.guest_profile
        except (GuestUser.DoesNotExist, AttributeError):
            return Response(
                {"error": "Guest profile not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        custom_user = guest.user
        custom_user.image_name = profile_image
        custom_user.avatar_version = (custom_user.avatar_version or 1) + 1
        custom_user.save(update_fields=["image_name", "avatar_version"])

        guest_data = GuestUserSerializer(
            guest,
            context={"request": request},
        ).data

        return Response(
            {
                "message": "Profile image updated successfully.",
                "guest": guest_data,
                "user": guest_data.get("user"),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path=r"profile/(?P<username>[^/.]+)", permission_classes=[IsAuthenticated])
    def profile(self, request, username=None):
        # Public-by-username view
        guest = GuestUser.objects.filter(
            user__username=username,
            is_active=True,
        ).select_related("user").first()

        if not guest:
            return Response(
                {"error": "Guest profile not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if guest.user.is_suspended:
            return Response(
                {"error": "This profile is suspended."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if guest.is_privacy and guest.user != request.user:
            serializer = LimitedGuestUserSerializer(guest, context={"request": request})
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = PublicGuestUserSerializer(guest, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path=r"profile/(?P<username>[^/.]+)/moments", permission_classes=[IsAuthenticated])
    def moments(self, request, username=None):
        # Public guest moments
        guest = GuestUser.objects.filter(
            user__username=username,
            is_active=True,
        ).select_related("user").first()

        if not guest:
            return Response(
                {"error": "Guest profile not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if guest.user.is_suspended:
            return Response(
                {"error": "This profile is suspended."},
                status=status.HTTP_403_FORBIDDEN,
            )

        viewer = request.user if request.user.is_authenticated else None

        qs = get_visible_posts(
            model=Moment,
            owner=guest,
            viewer=viewer,
        )

        serializer = MomentSerializer(
            qs,
            many=True,
            context={"request": request},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="view", permission_classes=[IsAuthenticated])
    def view_guest_profile(self, request, pk=None):
        # Backward-compatible detail view
        guest = GuestUser.objects.filter(
            pk=pk,
            is_active=True,
        ).select_related("user").first()

        if not guest:
            return Response(
                {"error": "Guest profile not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if guest.user.is_suspended:
            return Response(
                {"error": "This profile is suspended."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if guest.is_privacy and guest.user != request.user:
            serializer = LimitedGuestUserSerializer(guest, context={"request": request})
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = PublicGuestUserSerializer(guest, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)