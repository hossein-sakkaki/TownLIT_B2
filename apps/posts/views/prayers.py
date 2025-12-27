# apps/posts/views/prayers.py
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny

from apps.posts.models.pray import Pray
from apps.posts.serializers.prayers import PraySerializer
from apps.posts.mixins.mixins import  MemberActionMixin


# Pray ViewSet ---------------------------------------------------------------------------------------------------
class PrayViewSet(viewsets.ModelViewSet,  MemberActionMixin):
    queryset = Pray.objects.all()
    serializer_class = PraySerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'slug'

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_authenticated:
            return queryset.filter(is_active=True, is_hidden=False, is_restricted=False)
        
        member_user = getattr(self.request.user, 'member', None)

        if member_user:
            # Filter only active prays that are visible to members
            queryset = queryset.filter(
                content_type=ContentType.objects.get_for_model(member_user),
                object_id=member_user.id,
                is_active=True,
                is_hidden=False
            ).distinct()
        else:
            return Pray.objects.none()  # If not a member, return no results
        return queryset

    def perform_create(self, serializer):
        member = self.request.user.member
        serializer.save(
            content_type=ContentType.objects.get_for_model(member),
            object_id=member.id,
            published_at=timezone.now(),
            is_active=True
        )

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.content_object != self.request.user.member:
            return Response({"error": "You are not allowed to update this pray"}, status=status.HTTP_403_FORBIDDEN)
        instance = serializer.save(updated_at=timezone.now())
        return instance

    def perform_destroy(self, instance):
        if instance.content_object != self.request.user.member:
            return Response({"error": "You are not allowed to delete this pray"}, status=status.HTTP_403_FORBIDDEN)
        instance.delete()

    # Retrieve all active and visible prays for exploration
    @action(detail=False, methods=['get'], url_path='explore', permission_classes=[IsAuthenticated])
    def explore_prays(self, request):
        prays = Pray.objects.filter(is_active=True, is_hidden=False, is_restricted=False)
        serializer = PraySerializer(prays, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

