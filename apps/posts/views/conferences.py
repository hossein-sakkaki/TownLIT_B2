# apps/posts/views/conferences.py
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny

from apps.posts.models.conference import Conference
from apps.posts.models.lesson import Lesson
from apps.posts.serializers.conferences import ConferenceSerializer
from apps.posts.serializers.lessons import LessonSerializer
from apps.posts.mixins.mixins import  OrganizationActionMixin, ResourceManagementMixin
from apps.profilesOrg.models import (
    Organization, Church, MissionOrganization, ChristianPublishingHouse, ChristianCounselingCenter,
    ChristianWorshipMinistry, ChristianConferenceCenter, ChristianEducationalInstitution,
    ChristianChildrenOrganization, ChristianYouthOrganization, ChristianWomensOrganization, ChristianMensOrganization
)

# Conference ViewSet ---------------------------------------------------------------------------------------------------
class ConferenceViewSet(viewsets.ModelViewSet,  OrganizationActionMixin, ResourceManagementMixin):
    queryset = Conference.objects.all()
    serializer_class = ConferenceSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'slug'

    def get_queryset(self):
        queryset = super().get_queryset()
        organization_slug = self.kwargs.get('slug')
        
        # Check for organization and its subtypes (Church, etc.)
        organization = Organization.objects.filter(slug=organization_slug).first()
        if not organization:
            return Conference.objects.none()

        # Check if organization is restricted, only members can view restricted conferences
        if organization.is_restricted:
            member_user = getattr(self.request.user, 'member', None)
            if not member_user or not member_user.organization_memberships.filter(id=organization.id).exists():
                return Conference.objects.none()

        # Fetch conferences related to the organization or its subtypes
        organization_content_type = ContentType.objects.get_for_model(Organization)
        sub_organizations = [
            Church, MissionOrganization, ChristianPublishingHouse, ChristianCounselingCenter,
            ChristianWorshipMinistry, ChristianConferenceCenter, ChristianEducationalInstitution,
            ChristianChildrenOrganization, ChristianYouthOrganization, ChristianWomensOrganization, ChristianMensOrganization
        ]
        for sub_org_model in sub_organizations:
            sub_org = sub_org_model.objects.filter(organization=organization).first()
            if sub_org:
                sub_org_content_type = ContentType.objects.get_for_model(sub_org_model)
                return queryset.filter(
                    Q(content_type=organization_content_type, object_id=organization.id) |
                    Q(content_type=sub_org_content_type, object_id=sub_org.id),
                    is_active=True, is_hidden=False
                ).distinct()

        # Default to returning conferences for the main organization
        return queryset.filter(
            content_type=organization_content_type,
            object_id=organization.id,
            is_active=True,
            is_hidden=False
        ).distinct()

    def perform_create(self, serializer):
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        if not organization:
            return Response({"error": "Organization not found"}, status=status.HTTP_404_NOT_FOUND)
        
        # Check for sub-organization (Church, etc.)
        sub_organizations = [
            Church, MissionOrganization, ChristianPublishingHouse, ChristianCounselingCenter,
            ChristianWorshipMinistry, ChristianConferenceCenter, ChristianEducationalInstitution,
            ChristianChildrenOrganization, ChristianYouthOrganization, ChristianWomensOrganization, ChristianMensOrganization
        ]
        for sub_org_model in sub_organizations:
            sub_org = sub_org_model.objects.filter(organization=organization).first()
            if sub_org:
                content_type = ContentType.objects.get_for_model(sub_org_model)
                serializer.save(
                    content_type=content_type,
                    object_id=sub_org.id,
                    published_at=timezone.now(),
                    is_active=True
                )
                return

        # Default to saving for the main organization
        content_type = ContentType.objects.get_for_model(Organization)
        serializer.save(
            content_type=content_type,
            object_id=organization.id,
            published_at=timezone.now(),
            is_active=True
        )

    def perform_update(self, serializer):
        instance = self.get_object()
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        
        if instance.content_object != organization:
            return Response({"error": "You are not allowed to update this conference"}, status=status.HTTP_403_FORBIDDEN)
        serializer.save(updated_at=timezone.now())

    def perform_destroy(self, instance):
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        
        if instance.content_object != organization:
            return Response({"error": "You are not allowed to delete this conference"}, status=status.HTTP_403_FORBIDDEN)
        instance.delete()

    # Workshop Lesson Actions for Conference
    @action(detail=True, methods=['get'], url_path='lessons', permission_classes=[IsAuthenticated])
    def get_lessons(self, request, slug=None):
        conference = self.get_object()
        lessons = conference.workshops.all()
        serializer = LessonSerializer(lessons, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='add-workshop', permission_classes=[IsAuthenticated])
    def add_workshop(self, request, slug=None):
        conference = self.get_object()
        lesson_id = request.data.get('lesson_id')
        if conference.content_object != request.user:
            return Response({"error": "You are not allowed to add a workshop to this conference"}, status=status.HTTP_403_FORBIDDEN)
        try:
            lesson = Lesson.objects.get(id=lesson_id)
            conference.workshops.add(lesson)
            return Response({"message": "Lesson added successfully"}, status=status.HTTP_201_CREATED)
        except Lesson.DoesNotExist:
            return Response({"error": "Lesson not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'], url_path='remove-workshop', permission_classes=[IsAuthenticated])
    def remove_workshop(self, request, slug=None):
        conference = self.get_object()
        lesson_id = request.data.get('lesson_id')
        try:
            lesson = Lesson.objects.get(id=lesson_id)
            conference.workshops.remove(lesson)
            return Response({"message": "Lesson removed successfully"}, status=status.HTTP_204_NO_CONTENT)
        except Lesson.DoesNotExist:
            return Response({"error": "Lesson not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'], url_path='edit-workshop', permission_classes=[IsAuthenticated])
    def edit_workshop(self, request, slug=None):
        lesson_id = request.data.get('lesson_id')
        try:
            lesson = Lesson.objects.get(id=lesson_id)
            serializer = LessonSerializer(lesson, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Lesson.DoesNotExist:
            return Response({"error": "Lesson not found"}, status=status.HTTP_404_NOT_FOUND)


