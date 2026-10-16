# apps/organization_media/views/asset.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-28.
# Last Update by Hossein Sakkaki on 2026-09-28.

from django.shortcuts import get_object_or_404

from rest_framework import serializers, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from apps.organization_media.models import OrganizationMediaAsset
from apps.organization_media.serializers import OrganizationMediaAssetSerializer
from apps.organizations.constants import OrganizationPermissionKey
from apps.organizations.models import Organization
from apps.organizations.permissions import OrganizationsEnabledPermission
from apps.organizations.services.access import user_has_organization_permission


class OrganizationMediaAssetViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]
    serializer_class = OrganizationMediaAssetSerializer
    lookup_field = "public_id"
    lookup_url_kwarg = "public_id"

    def get_organization(self):
        if hasattr(self, "_organization"):
            return self._organization

        organization = get_object_or_404(
            Organization,
            slug=self.kwargs["slug"],
        )

        if not user_has_organization_permission(
            user=self.request.user,
            organization=organization,
            permission_key=OrganizationPermissionKey.MANAGE_PROFILE,
        ):
            raise PermissionDenied(
                "You do not have permission to manage organization media."
            )

        self._organization = organization
        return organization

    def get_queryset(self):
        queryset = OrganizationMediaAsset.objects.select_related(
            "organization",
            "created_by",
        ).filter(
            organization=self.get_organization()
        )

        kind = self.request.query_params.get("kind")
        if kind:
            kind = serializers.ChoiceField(
                choices=OrganizationMediaAsset.Kind.choices
            ).run_validation(kind)
            queryset = queryset.filter(kind=kind)

        asset_status = self.request.query_params.get("status")
        if asset_status:
            asset_status = serializers.ChoiceField(
                choices=OrganizationMediaAsset.Status.choices
            ).run_validation(asset_status)
            queryset = queryset.filter(status=asset_status)

        return queryset.order_by("-created_at", "-pk")