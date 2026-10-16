# apps/organizations/views/hierarchy.py
#
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-10-01.
#

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q

from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.constants import (
    OrganizationPermissionKey,
    OrganizationStatus,
    OrganizationVisibility,
)
from apps.organizations.models import Organization, OrganizationRelationship
from apps.organizations.permissions import OrganizationsEnabledPermission
from apps.organizations.selectors.bootstrap import organization_relationships_for_viewer
from apps.organizations.serializers import (
    OrganizationGovernanceProposalSerializer,
    OrganizationRelationshipCandidateSerializer,
    OrganizationRelationshipConsentProposalSerializer,
    OrganizationRelationshipCreateSerializer,
    OrganizationRelationshipSerializer,
)
from apps.organizations.services.access import user_has_organization_permission
from apps.organizations.services.hierarchy import (
    create_relationship_consent_proposal,
    request_organization_relationship,
)

from .access import get_visible_organization_or_404
from .helpers import raise_drf_validation_error


class OrganizationRelationshipCandidatesView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug):
        organization = get_visible_organization_or_404(
            user=request.user,
            slug=slug,
        )

        if (
            not getattr(request.user, "is_staff", False)
            and not user_has_organization_permission(
                user=request.user,
                organization=organization,
                permission_key=OrganizationPermissionKey.MANAGE_GOVERNANCE,
            )
        ):
            raise PermissionDenied(
                "You do not have permission to manage organization relationships."
            )

        query = (
            request.query_params.get("q", "")
            .strip()
        )

        if len(query) < 2:
            return Response([])

        queryset = (
            Organization.objects
            .filter(
                status=OrganizationStatus.ACTIVE,
                visibility=OrganizationVisibility.PUBLIC,
            )
            .exclude(pk=organization.pk)
            .filter(
                Q(name__icontains=query)
                | Q(short_name__icontains=query)
                | Q(slug__icontains=query)
            )
            .order_by("name", "id")[:25]
        )

        return Response(
            OrganizationRelationshipCandidateSerializer(
                queryset,
                many=True,
                context={"request": request},
            ).data
        )


class OrganizationRelationshipsView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug):
        organization = get_visible_organization_or_404(
            user=request.user,
            slug=slug,
        )

        return Response(
            OrganizationRelationshipSerializer(
                organization_relationships_for_viewer(
                    organization=organization,
                    user=request.user,
                ),
                many=True,
                context={"request": request},
            ).data
        )


class OrganizationRelationshipRequestView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request):
        serializer = OrganizationRelationshipCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        source = get_visible_organization_or_404(
            user=request.user,
            slug=data["source_organization_slug"],
        )
        target = get_visible_organization_or_404(
            user=request.user,
            slug=data["target_organization_slug"],
        )
        requested_by = get_visible_organization_or_404(
            user=request.user,
            slug=data["requested_by_organization_slug"],
        )

        try:
            relationship = request_organization_relationship(
                source_organization=source,
                target_organization=target,
                relationship_type=data["relationship_type"],
                actor=request.user,
                requested_by_organization=requested_by,
                metadata=data.get("metadata"),
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            OrganizationRelationshipSerializer(
                relationship,
                context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )


class OrganizationRelationshipDetailView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, public_id):
        relationship = (
            OrganizationRelationship.objects
            .select_related(
                "source_organization",
                "target_organization",
                "requested_by_organization",
            )
            .prefetch_related("consents__organization")
            .filter(public_id=public_id)
            .first()
        )
        if not relationship:
            raise NotFound("Organization relationship not found.")

        visible_from_source = organization_relationships_for_viewer(
            organization=relationship.source_organization,
            user=request.user,
        ).filter(pk=relationship.pk).exists()
        visible_from_target = organization_relationships_for_viewer(
            organization=relationship.target_organization,
            user=request.user,
        ).filter(pk=relationship.pk).exists()

        if not visible_from_source and not visible_from_target:
            raise NotFound("Organization relationship not found.")

        return Response(
            OrganizationRelationshipSerializer(
                relationship,
                context={"request": request},
            ).data
        )


class OrganizationRelationshipConsentProposalView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, public_id):
        relationship = OrganizationRelationship.objects.filter(
            public_id=public_id
        ).first()
        if not relationship:
            raise NotFound("Organization relationship not found.")

        serializer = OrganizationRelationshipConsentProposalSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        organization = Organization.objects.filter(
            slug=serializer.validated_data["organization_slug"]
        ).first()
        if not organization:
            raise NotFound("Organization not found.")

        try:
            proposal = create_relationship_consent_proposal(
                relationship=relationship,
                organization=organization,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            OrganizationGovernanceProposalSerializer(
                proposal,
                context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )

