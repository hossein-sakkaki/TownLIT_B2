# apps/posts/views/missions.py
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status, viewsets

from apps.posts.models.service_event import ServiceEvent
from apps.posts.serializers.service_events import ServiceEventSerializer
from apps.posts.mixins.mixins import  OrganizationActionMixin
from apps.profilesOrg.models import (
    Organization, Church, MissionOrganization, ChristianPublishingHouse, ChristianCounselingCenter,
    ChristianWorshipMinistry, ChristianConferenceCenter, ChristianEducationalInstitution,
    ChristianChildrenOrganization, ChristianYouthOrganization, ChristianWomensOrganization, ChristianMensOrganization
)





# SERVICE EVENT ViewSet ---------------------------------------------------------------------------------------------------
class ServiceEventViewSet(viewsets.ModelViewSet,  OrganizationActionMixin):
    queryset = ServiceEvent.objects.all()
    serializer_class = ServiceEventSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'slug'

    def get_queryset(self):
        queryset = super().get_queryset()
        organization_slug = self.kwargs.get('slug')
        
        # Check for organization and its subtypes (Church, MissionOrganization, etc.)
        organization = Organization.objects.filter(slug=organization_slug).first()
        if not organization:
            return ServiceEvent.objects.none()

        # Check if organization is restricted, only members can view restricted service events
        if organization.is_restricted:
            member_user = getattr(self.request.user, 'member', None)
            if not member_user or not member_user.organization_memberships.filter(id=organization.id).exists():
                return ServiceEvent.objects.none()  # If not a member of the organization, return empty queryset

        # Fetch service events related to the organization or its subtypes
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

        # Default to returning service events for the main organization
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
        
        # Check for sub-organization (Church, MissionOrganization, etc.)
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
                    is_active=True
                )
                return

        # Default to saving for the main organization
        content_type = ContentType.objects.get_for_model(Organization)
        serializer.save(
            content_type=content_type,
            object_id=organization.id,
            is_active=True
        )

    def perform_update(self, serializer):
        instance = self.get_object()
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        
        if instance.content_object != organization:
            return Response({"error": "You are not allowed to update this service event"}, status=status.HTTP_403_FORBIDDEN)
        serializer.save()

    def perform_destroy(self, instance):
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        
        if instance.content_object != organization:
            return Response({"error": "You are not allowed to delete this service event"}, status=status.HTTP_403_FORBIDDEN)
        instance.delete()

