# apps/organizations/selectors/bootstrap.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

from django.db.models import Q

from apps.organizations.constants import (
    MembershipRequestStatus,
    OrganizationGovernanceProposalStatus,
    OrganizationPermissionKey,
    OrganizationRelationshipStatus,
    OrganizationRoleScope,
)
from apps.organizations.models import (
    OrganizationGovernanceProposal,
    OrganizationRelationship,
)
from apps.organizations.services.access import (
    get_current_membership_for_user,
    user_has_organization_permission,
)


ORGANIZATION_PERMISSION_KEYS = (
    OrganizationPermissionKey.VIEW_ADMIN,
    OrganizationPermissionKey.MANAGE_PROFILE,
    OrganizationPermissionKey.MANAGE_MEMBERS,
    OrganizationPermissionKey.MANAGE_ROLES,
    OrganizationPermissionKey.MANAGE_CONTENT,
    OrganizationPermissionKey.MANAGE_ANNOUNCEMENTS,
    OrganizationPermissionKey.MANAGE_MODULES,
    OrganizationPermissionKey.MANAGE_BILLING,
    OrganizationPermissionKey.MANAGE_VERIFICATION,
    OrganizationPermissionKey.MANAGE_GOVERNANCE,
    OrganizationPermissionKey.MANAGE_SETTINGS,
)


def viewer_organization_permissions(*, organization, user):
    return [
        permission_key
        for permission_key in ORGANIZATION_PERMISSION_KEYS
        if user_has_organization_permission(
            user=user,
            organization=organization,
            permission_key=permission_key,
            scope_type=OrganizationRoleScope.ORGANIZATION,
            scope_key="",
        )
    ]


def viewer_membership_context(*, organization, user):
    membership = get_current_membership_for_user(
        organization=organization,
        user=user,
    )

    pending_request = None
    member = getattr(user, "member_profile", None)

    if member:
        pending_request = (
            organization.membership_requests
            .filter(
                member=member,
                status=MembershipRequestStatus.PENDING,
            )
            .order_by("-created_at")
            .first()
        )

    connection = (
        organization.connections
        .filter(
            user=user,
            status="active",
        )
        .first()
    )

    return {
        "connection": connection,
        "membership": membership,
        "pending_request": pending_request,
    }


def organization_relationships_for_viewer(*, organization, user):
    queryset = (
        OrganizationRelationship.objects
        .select_related(
            "source_organization",
            "target_organization",
            "requested_by_organization",
        )
        .prefetch_related("consents__organization")
        .filter(
            Q(source_organization=organization)
            | Q(target_organization=organization)
        )
    )

    can_manage = user_has_organization_permission(
        user=user,
        organization=organization,
        permission_key=OrganizationPermissionKey.MANAGE_GOVERNANCE,
    )

    if not can_manage and not getattr(user, "is_staff", False):
        queryset = queryset.filter(
            status=OrganizationRelationshipStatus.ACTIVE,
        )

    return queryset.order_by("-created_at", "-id")


def governance_proposals_for_viewer(*, organization, user):
    queryset = (
        OrganizationGovernanceProposal.objects
        .select_related(
            "organization",
            "rule",
            "target_membership",
            "relationship",
        )
        .prefetch_related(
            "electors",
            "votes__elector",
        )
        .filter(organization=organization)
    )

    can_view_admin = user_has_organization_permission(
        user=user,
        organization=organization,
        permission_key=OrganizationPermissionKey.VIEW_ADMIN,
    )
    can_manage_governance = user_has_organization_permission(
        user=user,
        organization=organization,
        permission_key=OrganizationPermissionKey.MANAGE_GOVERNANCE,
    )

    if (
        can_view_admin
        or can_manage_governance
        or getattr(user, "is_staff", False)
    ):
        return queryset.order_by("-created_at", "-id")

    return (
        queryset
        .filter(
            electors__user=user,
            electors__is_eligible=True,
        )
        .distinct()
        .order_by("-created_at", "-id")
    )


def open_governance_proposals_for_viewer(*, organization, user):
    return governance_proposals_for_viewer(
        organization=organization,
        user=user,
    ).filter(
        status__in=(
            OrganizationGovernanceProposalStatus.DRAFT,
            OrganizationGovernanceProposalStatus.OPEN,
        )
    )
