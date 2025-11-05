# apps/posts/views/announcements.py
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny

from apps.posts.models import Announcement
from apps.posts.serializers.announcements import AnnouncementSerializer
from apps.posts.mixins.mixins import CommentMixin, OrganizationActionMixin
from apps.profilesOrg.models import Organization


# Announcement ViewSet ---------------------------------------------------------------------------------------------------
class AnnouncementViewSet(viewsets.ModelViewSet, CommentMixin, OrganizationActionMixin):
    queryset = Announcement.objects.all()
    serializer_class = AnnouncementSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'slug'

    def get_queryset(self):
        queryset = super().get_queryset()
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        if not organization:
            return Announcement.objects.none()  # If the organization doesn't exist, return an empty queryset

        return queryset.filter(
            content_type=ContentType.objects.get_for_model(Organization),
            object_id=organization.id,
            is_active=True,
            is_hidden=False
        ).distinct()

    def perform_create(self, serializer):
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        if not organization:
            return Response({"error": "Organization not found"}, status=status.HTTP_404_NOT_FOUND)
        
        serializer.save(
            content_type=ContentType.objects.get_for_model(organization),
            object_id=organization.id,
            created_at=timezone.now(),
            is_active=True
        )

    def perform_update(self, serializer):
        instance = self.get_object()
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        
        if instance.content_object != organization:
            return Response({"error": "You are not allowed to update this announcement"}, status=status.HTTP_403_FORBIDDEN)
        
        serializer.save(updated_at=timezone.now())

    def perform_destroy(self, instance):
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        
        if instance.content_object != organization:
            return Response({"error": "You are not allowed to delete this announcement"}, status=status.HTTP_403_FORBIDDEN)
        
        instance.delete()

