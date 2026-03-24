# apps/profiles/views/profile_me_view.py

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.profiles.services.active_profile import get_active_profile
from apps.profiles.serializers.profile_me_serializer import ProfileMeSerializer


class ProfileMeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        active = get_active_profile(user)

        data = {
            "profile_type": active.profile_type,
            "profile_id": active.profile.id if active.profile else None,
            "username": user.username,
            "is_member": bool(user.is_member),
        }

        serializer = ProfileMeSerializer(data)
        return Response(serializer.data)