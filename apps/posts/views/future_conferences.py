# apps/posts/views/future_conferences.py
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny

from apps.posts.models import FutureConference
from apps.posts.serializers.future_conferences import FutureConferenceSerializer
from apps.posts.mixins.mixins import CommentMixin, OrganizationActionMixin
from apps.profilesOrg.models import (
    Organization, Church, MissionOrganization, ChristianPublishingHouse, ChristianCounselingCenter,
    ChristianWorshipMinistry, ChristianConferenceCenter, ChristianEducationalInstitution,
    ChristianChildrenOrganization, ChristianYouthOrganization, ChristianWomensOrganization, ChristianMensOrganization
)


# Future Conference ViewSet ---------------------------------------------------------------------------------------------------
class FutureConferenceViewSet(viewsets.ModelViewSet, CommentMixin, OrganizationActionMixin):
    queryset = FutureConference.objects.all()
    serializer_class = FutureConferenceSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'slug'

    def get_queryset(self):
        queryset = super().get_queryset()
        organization_slug = self.kwargs.get('slug')
        
        organization = Organization.objects.filter(slug=organization_slug).first()
        if not organization:
            return FutureConference.objects.none()

        if organization.is_restricted:
            member_user = getattr(self.request.user, 'member', None)
            if not member_user or not member_user.organization_memberships.filter(id=organization.id).exists():
                return FutureConference.objects.none()

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
            return Response({"error": "You are not allowed to update this future conference"}, status=status.HTTP_403_FORBIDDEN)
        serializer.save(updated_at=timezone.now())

    def perform_destroy(self, instance):
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        
        if instance.content_object != organization:
            return Response({"error": "You are not allowed to delete this future conference"}, status=status.HTTP_403_FORBIDDEN)
        instance.delete()

    # Explore Future Conferences
    @action(detail=False, methods=['get'], url_path='explore', permission_classes=[IsAuthenticated])
    def explore_future_conferences(self, request):
        future_conferences = FutureConference.objects.filter(is_active=True, is_hidden=False)
        serializer = self.get_serializer(future_conferences, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # Search Future Conferences by name or description
    @action(detail=False, methods=['get'], url_path='search', permission_classes=[IsAuthenticated])
    def search_future_conferences(self, request):
        query = request.query_params.get('q', None)
        if query:
            future_conferences = FutureConference.objects.filter(
                Q(conference_name__icontains=query) |
                Q(conference_description__icontains=query),
                is_active=True, is_hidden=False
            )
        else:
            future_conferences = FutureConference.objects.filter(is_active=True, is_hidden=False)
        
        serializer = self.get_serializer(future_conferences, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
