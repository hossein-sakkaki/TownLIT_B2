# apps/profiles/views/profile_me_view.py

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.profiles.models.member import Member
from apps.profiles.models.guest import GuestUser
from apps.profiles.services.active_profile import get_active_profile
from apps.profiles.serializers.profile_me_serializer import ProfileMeSerializer


class ProfileMeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if getattr(user, "is_deleted", False):
            return Response(
                {
                    "error": "Your account is deactivated. Reactivate first to access your profile.",
                    "code": "account_deactivated",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        active = get_active_profile(user)

        owner_profile_access_mode = "normal"
        profile_gate = None

        profile_type = active.profile_type
        profile = active.profile

        if profile is None:
            owner_profile_access_mode = "missing"

        elif profile_type == "member":
            # Important:
            # This endpoint must stay lightweight.
            # Do NOT serialize the full Member profile here.
            #
            # Safety gate:
            # Same neutral gate used by MemberViewSet._limited_self_profile_response.
            if getattr(profile, "is_hidden_by_confidants", False):
                owner_profile_access_mode = "restricted"
                profile_gate = {
                    "key": "profile_temporarily_unavailable",
                    "reason": "temporarily_unavailable",
                    "redirect_to": f"/lit/{user.username}",
                    "owner_message": "Your profile is currently unavailable. Please contact TownLIT Support for more information.",
                }

        elif profile_type == "guest":
            # Guest owner profile currently has no equivalent hidden-by-confidants gate.
            owner_profile_access_mode = "normal"

        data = {
            "profile_type": profile_type,
            "profile_id": profile.id if profile else None,
            "username": user.username,
            "is_member": bool(user.is_member),

            "owner_profile_access_mode": owner_profile_access_mode,
            "profile_gate": profile_gate,

            "is_account_paused": bool(getattr(user, "is_account_paused", False)),
            "is_suspended": bool(getattr(user, "is_suspended", False)),
        }

        serializer = ProfileMeSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)

# # apps/profiles/views/profile_me_view.py

# from rest_framework.views import APIView
# from rest_framework.permissions import IsAuthenticated
# from rest_framework.response import Response

# from apps.profiles.services.active_profile import get_active_profile
# from apps.profiles.serializers.profile_me_serializer import ProfileMeSerializer


# class ProfileMeView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         user = request.user
#         active = get_active_profile(user)

#         data = {
#             "profile_type": active.profile_type,
#             "profile_id": active.profile.id if active.profile else None,
#             "username": user.username,
#             "is_member": bool(user.is_member),
#         }

#         serializer = ProfileMeSerializer(data)
#         return Response(serializer.data)