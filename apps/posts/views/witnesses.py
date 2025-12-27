# apps/posts/views/witnesses.py
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny

from apps.posts.models.witness import Witness
from apps.posts.serializers.witnesses import WitnessSerializer
from apps.posts.mixins.mixins import  OrganizationActionMixin
from apps.profilesOrg.models import Organization


# Witness ViewSet ---------------------------------------------------------------------------------------------------
class WitnessViewSet(viewsets.ModelViewSet,  OrganizationActionMixin):
    queryset = Witness.objects.all()
    serializer_class = WitnessSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'slug'

    def get_queryset(self):
        queryset = super().get_queryset()
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        if not organization:
            return Witness.objects.none()

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
            re_published_at=timezone.now(),
            is_active=True
        )

    def perform_update(self, serializer):
        instance = self.get_object()
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        
        if instance.content_object != organization:
            return Response({"error": "You are not allowed to update this witness"}, status=status.HTTP_403_FORBIDDEN)
        
        serializer.save()

    def perform_destroy(self, instance):
        organization_slug = self.kwargs.get('slug')
        organization = Organization.objects.filter(slug=organization_slug).first()
        
        if instance.content_object != organization:
            return Response({"error": "You are not allowed to delete this witness"}, status=status.HTTP_403_FORBIDDEN)
        
        instance.delete()

    # Action for retrieving related testimonies for the witness
    @action(detail=True, methods=['get'], url_path='testimonies', permission_classes=[IsAuthenticated])
    def get_testimonies(self, request, slug=None):
        witness = self.get_object()
        testimonies = witness.testimony.all()  # Retrieve related testimonies
        return Response({
            "witness": witness.title,
            "testimonies": [str(testimony) for testimony in testimonies]
        }, status=status.HTTP_200_OK)

