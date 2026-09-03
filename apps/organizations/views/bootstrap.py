# apps/organizations/views/bootstrap.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

from django.db.models import Count, Q
from django.utils import timezone

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.api_contract import ORGANIZATIONS_API_CONTRACT_VERSION
from apps.organizations.constants import (
    ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES,
    OrganizationGovernanceAction,
    OrganizationKind,
    OrganizationModuleActivationStatus,
    OrganizationModuleVisibility,
    OrganizationPermissionKey,
    OrganizationRelationshipType,
    OrganizationVerificationPath,
)
from apps.organizations.feature_flags import (
    organization_android_enabled,
    organization_creation_enabled,
    organization_governance_enabled,
    organization_ios_enabled,
    organization_hierarchy_enabled,
    organization_modules_enabled,
    organization_verification_enabled,
    organization_web_admin_enabled,
    organizations_enabled,
)
from apps.organizations.models import Organization
from apps.organizations.permissions import OrganizationsEnabledPermission
from apps.organizations.selectors.bootstrap import (
    open_governance_proposals_for_viewer,
    organization_relationships_for_viewer,
    viewer_membership_context,
    viewer_organization_permissions,
)
from apps.organizations.selectors.modules import (
    organization_module_catalog_queryset,
)
from apps.organizations.selectors.verification import (
    get_organization_verification_summary,
)
from apps.organizations.serializers import (
    OrganizationGovernanceProposalSerializer,
    OrganizationMembershipRequestSerializer,
    OrganizationMembershipSerializer,
    OrganizationModuleAccessSerializer,
    OrganizationModuleDefinitionSerializer,
    OrganizationRelationshipSerializer,
    OrganizationRoleAssignmentSerializer,
    OrganizationSerializer,
)
from apps.organizations.services.access import user_has_organization_permission
from apps.organizations.services.eligibility import (
    get_organization_creation_eligibility,
)
from apps.organizations.services.modules import (
    get_organization_module_access,
)


def _choice_payload(choices):
    return [
        {"key": value, "label": label}
        for value, label in choices
    ]


def _feature_payload():
    return {
        "enabled": organizations_enabled(),
        "creation": organization_creation_enabled(),
        "verification": organization_verification_enabled(),
        "hierarchy": organization_hierarchy_enabled(),
        "governance": organization_governance_enabled(),
        "modules": organization_modules_enabled(),
        "clients": {
            "ios": organization_ios_enabled(),
            "android": organization_android_enabled(),
            "web_admin": organization_web_admin_enabled(),
        },
    }


def _module_access_payload(*, organization, actor, definition):
    access = get_organization_module_access(
        organization=organization,
        module_key=definition.key,
        actor=actor,
    )
    activation = access.activation

    return {
        "key": definition.key,
        "name": definition.name,
        "description": definition.description,
        "status": activation.status if activation else None,
        "visibility": activation.visibility if activation else None,
        "access_mode": access.access_mode,
        "reason": access.reason,
        "is_verified": access.is_verified,
        "has_entitlement": access.has_entitlement,
        "can_manage": access.can_manage,
        "can_write": access.can_write,
        "activated": activation is not None,
        "activation_public_id": (
            activation.public_id if activation else None
        ),
        "display_name": (
            activation.display_name if activation else None
        ),
        "summary": activation.summary if activation else None,
        "schema_version": definition.schema_version,
    }


class OrganizationPlatformBootstrapView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request):
        eligibility = get_organization_creation_eligibility(
            request.user
        )
        modules = []

        if organization_modules_enabled():
            modules = OrganizationModuleDefinitionSerializer(
                organization_module_catalog_queryset(public_only=True),
                many=True,
            ).data

        return Response({
            "contract_version": ORGANIZATIONS_API_CONTRACT_VERSION,
            "features": _feature_payload(),
            "creation_eligibility": {
                "eligible": eligibility.eligible,
                "code": eligibility.code,
                "detail": eligibility.detail,
            },
            "organization_kinds": _choice_payload(
                OrganizationKind.choices
            ),
            "verification_paths": _choice_payload(
                OrganizationVerificationPath.choices
            ),
            "relationship_types": _choice_payload(
                OrganizationRelationshipType.choices
            ),
            "governance_actions": _choice_payload(
                OrganizationGovernanceAction.choices
            ),
            "module_catalog": modules,
        })


class OrganizationBootstrapView(APIView):
    permission_classes = [
        IsAuthenticated,
        OrganizationsEnabledPermission,
    ]

    def get(self, request, slug):
        organization = (
            Organization.objects
            .select_related("subscription_account")
            .annotate(
                follower_count=Count(
                    "connections",
                    filter=Q(
                        connections__status="active",
                        connections__relationship_type="follower",
                    ),
                    distinct=True,
                ),
                member_count=Count(
                    "memberships",
                    filter=Q(memberships__status="active"),
                    distinct=True,
                ),
            )
            .filter(slug=slug)
            .first()
        )

        if not organization:
            from rest_framework.exceptions import NotFound

            raise NotFound("Organization not found.")

        # Reuse the public/member visibility policy from the main endpoint.
        from apps.organizations.constants import (
            CURRENT_MEMBERSHIP_STATUSES,
            OrganizationStatus,
            OrganizationVisibility,
        )

        if not getattr(request.user, "is_staff", False):
            is_current_member = organization.memberships.filter(
                member__user=request.user,
                status__in=CURRENT_MEMBERSHIP_STATUSES,
            ).exists()

            is_visible = (
                organization.status == OrganizationStatus.ACTIVE
                and organization.visibility in {
                    OrganizationVisibility.PUBLIC,
                    OrganizationVisibility.UNLISTED,
                }
            )

            if not is_current_member and not is_visible:
                from rest_framework.exceptions import NotFound

                raise NotFound("Organization not found.")

        viewer = viewer_membership_context(
            organization=organization,
            user=request.user,
        )
        permissions = viewer_organization_permissions(
            organization=organization,
            user=request.user,
        )

        role_assignments = []
        if viewer["membership"]:
            now = timezone.now()
            assignments = (
                viewer["membership"].role_assignments
                .select_related("role")
                .prefetch_related("role__permissions")
                .filter(
                    is_active=True,
                    revoked_at__isnull=True,
                    starts_at__lte=now,
                    role__is_active=True,
                )
                .filter(
                    Q(ends_at__isnull=True)
                    | Q(ends_at__gt=now)
                )
                .order_by("-role__priority", "id")
            )
            role_assignments = OrganizationRoleAssignmentSerializer(
                assignments,
                many=True,
                context={"request": request},
            ).data

        pending_request = None
        if viewer["pending_request"]:
            pending_request = OrganizationMembershipRequestSerializer(
                viewer["pending_request"],
                context={"request": request},
            ).data

        membership = None
        if viewer["membership"]:
            membership = OrganizationMembershipSerializer(
                viewer["membership"],
                context={"request": request},
            ).data

        modules = []
        if organization_modules_enabled():
            definitions = organization_module_catalog_queryset(
                public_only=False,
            )
            module_payloads = [
                _module_access_payload(
                    organization=organization,
                    actor=request.user,
                    definition=definition,
                )
                for definition in definitions
            ]

            can_manage_all_modules = user_has_organization_permission(
                user=request.user,
                organization=organization,
                permission_key=OrganizationPermissionKey.MANAGE_MODULES,
            )
            current_membership = viewer["membership"]
            is_active_member = bool(
                current_membership
                and current_membership.status
                in ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES
            )

            visible_module_payloads = []
            for item in module_payloads:
                if getattr(request.user, "is_staff", False) or can_manage_all_modules:
                    visible_module_payloads.append(item)
                    continue

                if item["can_manage"]:
                    visible_module_payloads.append(item)
                    continue

                if not item["activated"]:
                    continue

                if item["status"] != OrganizationModuleActivationStatus.ENABLED:
                    continue

                if item["visibility"] == OrganizationModuleVisibility.PUBLIC:
                    visible_module_payloads.append(item)
                    continue

                if (
                    is_active_member
                    and item["visibility"]
                    == OrganizationModuleVisibility.MEMBERS_ONLY
                ):
                    visible_module_payloads.append(item)

            viewer_can_manage_modules = bool(
                getattr(request.user, "is_staff", False)
                or can_manage_all_modules
            )
            if not viewer_can_manage_modules:
                visible_module_payloads = [
                    {**item, "has_entitlement": None}
                    if not item["can_manage"]
                    else item
                    for item in visible_module_payloads
                ]

            modules = OrganizationModuleAccessSerializer(
                visible_module_payloads,
                many=True,
            ).data

        relationships = []
        if organization_hierarchy_enabled():
            relationships = OrganizationRelationshipSerializer(
                organization_relationships_for_viewer(
                    organization=organization,
                    user=request.user,
                ),
                many=True,
                context={"request": request},
            ).data

        open_proposals = []
        if organization_governance_enabled():
            open_proposals = OrganizationGovernanceProposalSerializer(
                open_governance_proposals_for_viewer(
                    organization=organization,
                    user=request.user,
                ),
                many=True,
                context={"request": request},
            ).data

        return Response({
            "contract_version": ORGANIZATIONS_API_CONTRACT_VERSION,
            "features": _feature_payload(),
            "organization": OrganizationSerializer(
                organization,
                context={"request": request},
            ).data,
            "viewer": {
                "is_platform_staff": bool(
                    getattr(request.user, "is_staff", False)
                ),
                "relationship": (
                    viewer["connection"].relationship_type
                    if viewer["connection"]
                    else None
                ),
                "membership": membership,
                "pending_membership_request": pending_request,
                "permissions": permissions,
                "role_assignments": role_assignments,
            },
            "verification": (
                get_organization_verification_summary(
                    organization=organization,
                )
                if organization_verification_enabled()
                else {
                    "is_verified": False,
                    "grant_type": None,
                    "verified_at": None,
                    "expires_at": None,
                    "authority_organization": None,
                }
            ),
            "modules": modules,
            "relationships": relationships,
            "open_governance_proposals": open_proposals,
        })
