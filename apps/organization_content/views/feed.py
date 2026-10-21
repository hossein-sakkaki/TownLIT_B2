# apps/organization_content/views/feed.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-27.
# Last Update by Hossein Sakkaki on 2026-10-19.

from django.shortcuts import get_object_or_404

from rest_framework import viewsets
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.organization_content.serializers import (
    PublicOrganizationFeedEntrySerializer,
)
from apps.organization_content.services.feed import visible_feed
from apps.organization_content.services.access import can_view_organization_content
from apps.organizations.constants import OrganizationStatus, OrganizationVisibility
from apps.organizations.models import Organization


class PublicOrganizationFeedViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    def list(self, request, slug=None):
        organization = get_object_or_404(
            Organization,
            slug=slug,
            status=OrganizationStatus.ACTIVE,
            visibility__in=[OrganizationVisibility.PUBLIC, OrganizationVisibility.UNLISTED],
        )
        if not can_view_organization_content(organization=organization, viewer=request.user):
            raise NotFound("Organization not found.")

        entries = visible_feed(organization, viewer=request.user)

        return Response({
            "organization_public_id": str(organization.public_id),
            "results": PublicOrganizationFeedEntrySerializer(
                entries,
                many=True,
                context={"request": request},
            ).data,
        })
