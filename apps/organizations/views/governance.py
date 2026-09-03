# apps/organizations/views/governance.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.constants import (
    OrganizationGovernanceAction,
    OrganizationPermissionKey,
)
from apps.organizations.models import (
    OrganizationGovernanceProposal,
    OrganizationMembership,
    OrganizationRelationship,
)
from apps.organizations.permissions import OrganizationsEnabledPermission
from apps.organizations.selectors.bootstrap import governance_proposals_for_viewer
from apps.organizations.serializers import (
    OrganizationGovernanceDecisionSerializer,
    OrganizationGovernanceProposalCreateSerializer,
    OrganizationGovernanceProposalSerializer,
    OrganizationGovernanceRuleSerializer,
    OrganizationGovernanceVoteSerializer,
)
from apps.organizations.services.access import user_has_organization_permission
from apps.organizations.services.governance import (
    cancel_governance_proposal,
    cast_governance_vote,
    create_governance_proposal,
    finalize_governance_proposal,
    open_governance_proposal,
)

from .access import get_visible_organization_or_404
from .helpers import raise_drf_validation_error


def _get_visible_proposal(user, public_id):
    proposal = (
        OrganizationGovernanceProposal.objects
        .select_related(
            "organization",
            "rule",
            "target_membership",
            "relationship",
        )
        .prefetch_related("electors", "votes__elector")
        .filter(public_id=public_id)
        .first()
    )
    if not proposal:
        raise NotFound("Governance proposal not found.")

    visible = governance_proposals_for_viewer(
        organization=proposal.organization,
        user=user,
    ).filter(pk=proposal.pk).exists()

    if not visible:
        raise NotFound("Governance proposal not found.")

    return proposal


class OrganizationGovernanceRulesView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug):
        organization = get_visible_organization_or_404(
            user=request.user,
            slug=slug,
        )

        if not user_has_organization_permission(
            user=request.user,
            organization=organization,
            permission_key=OrganizationPermissionKey.VIEW_ADMIN,
        ):
            raise PermissionDenied(
                "You do not have permission to view organization governance rules."
            )

        return Response(
            OrganizationGovernanceRuleSerializer(
                organization.governance_rules.filter(is_active=True),
                many=True,
            ).data
        )


class OrganizationGovernanceProposalsView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, slug):
        organization = get_visible_organization_or_404(
            user=request.user,
            slug=slug,
        )
        return Response(
            OrganizationGovernanceProposalSerializer(
                governance_proposals_for_viewer(
                    organization=organization,
                    user=request.user,
                ),
                many=True,
                context={"request": request},
            ).data
        )

    def post(self, request, slug):
        organization = get_visible_organization_or_404(
            user=request.user,
            slug=slug,
        )
        serializer = OrganizationGovernanceProposalCreateSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)

        if (
            data["action_key"]
            == OrganizationGovernanceAction.RELATIONSHIP_CONSENT
        ):
            from rest_framework.exceptions import ValidationError

            raise ValidationError({
                "action_key": (
                    "Relationship consent proposals must be created "
                    "through the relationship consent workflow."
                ),
            })

        target_membership = None
        target_public_id = data.pop("target_membership_public_id", None)
        if target_public_id:
            target_membership = OrganizationMembership.objects.filter(
                organization=organization,
                public_id=target_public_id,
            ).first()
            if not target_membership:
                raise NotFound("Target membership not found.")

        relationship = None
        relationship_public_id = data.pop("relationship_public_id", None)
        if relationship_public_id:
            relationship = OrganizationRelationship.objects.filter(
                public_id=relationship_public_id,
            ).first()
            if not relationship:
                raise NotFound("Organization relationship not found.")

        try:
            proposal = create_governance_proposal(
                organization=organization,
                actor=request.user,
                target_membership=target_membership,
                relationship=relationship,
                **data,
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


class OrganizationGovernanceProposalDetailView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def get(self, request, public_id):
        proposal = _get_visible_proposal(request.user, public_id)
        return Response(
            OrganizationGovernanceProposalSerializer(
                proposal,
                context={"request": request},
            ).data
        )


class OrganizationGovernanceProposalOpenView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, public_id):
        proposal = _get_visible_proposal(request.user, public_id)
        try:
            proposal = open_governance_proposal(
                proposal=proposal,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            OrganizationGovernanceProposalSerializer(
                proposal,
                context={"request": request},
            ).data
        )


class OrganizationGovernanceProposalVoteView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, public_id):
        proposal = _get_visible_proposal(request.user, public_id)
        serializer = OrganizationGovernanceVoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            vote = cast_governance_vote(
                actor=request.user,
                proposal=proposal,
                choice=serializer.validated_data["choice"],
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response({
            "proposal_public_id": str(proposal.public_id),
            "choice": vote.choice,
            "cast_at": vote.cast_at,
        })


class OrganizationGovernanceProposalFinalizeView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, public_id):
        proposal = _get_visible_proposal(request.user, public_id)
        try:
            decision = finalize_governance_proposal(
                proposal=proposal,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        proposal.refresh_from_db()
        return Response({
            "proposal": OrganizationGovernanceProposalSerializer(
                proposal,
                context={"request": request},
            ).data,
            "decision": OrganizationGovernanceDecisionSerializer(
                decision
            ).data,
        })


class OrganizationGovernanceProposalCancelView(APIView):
    permission_classes = [IsAuthenticated, OrganizationsEnabledPermission]

    def post(self, request, public_id):
        proposal = _get_visible_proposal(request.user, public_id)
        try:
            proposal = cancel_governance_proposal(
                proposal=proposal,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation_error(exc)

        return Response(
            OrganizationGovernanceProposalSerializer(
                proposal,
                context={"request": request},
            ).data
        )
