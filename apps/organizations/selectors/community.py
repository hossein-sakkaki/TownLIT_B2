# apps/organizations/selectors/community.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-05.
# Last Update by Hossein Sakkaki on 2026-10-05.
#

from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.core.boundaries.services.policy import BoundaryPolicy
from apps.organizations.constants import (
    OrganizationConnectionStatus,
    OrganizationConnectionType,
    OrganizationMembershipStatus,
)
from apps.organizations.models import (
    OrganizationConnection,
    OrganizationMembership,
)


User = get_user_model()

ORGANIZATION_COMMUNITY_MEMBERS = "members"
ORGANIZATION_COMMUNITY_FOLLOWERS = "followers"

ORGANIZATION_COMMUNITY_AUDIENCES = {
    ORGANIZATION_COMMUNITY_MEMBERS,
    ORGANIZATION_COMMUNITY_FOLLOWERS,
}


def visible_organization_community_users(
    *,
    organization,
    viewer,
    audience,
):
    """
    Return public-safe users for an Organization Community surface.

    The Organization relationship counters are broader than this list:
    private, suspended, paused, deleted, safety-hidden, inactive, and
    Boundary-hidden profiles remain excluded from public Community output.
    """
    if audience == ORGANIZATION_COMMUNITY_MEMBERS:
        user_ids = (
            OrganizationMembership.objects
            .filter(
                organization=organization,
                status=OrganizationMembershipStatus.ACTIVE,
            )
            .values_list(
                "member__user_id",
                flat=True,
            )
        )
    elif audience == ORGANIZATION_COMMUNITY_FOLLOWERS:
        user_ids = (
            OrganizationConnection.objects
            .filter(
                organization=organization,
                status=OrganizationConnectionStatus.ACTIVE,
                relationship_type=OrganizationConnectionType.FOLLOWER,
            )
            .values_list(
                "user_id",
                flat=True,
            )
        )
    else:
        return User.objects.none()

    boundary_excluded_ids = set(
        BoundaryPolicy.user_ids_with_boundary_between(
            viewer
        )
    )

    public_profile_filter = (
        Q(
            is_member=True,
            member_profile__is_active=True,
            member_profile__is_privacy=False,
            member_profile__is_hidden_by_confidants=False,
        )
        | Q(
            is_member=False,
            guest_profile__is_active=True,
            guest_profile__is_privacy=False,
        )
    )

    queryset = (
        User.objects
        .filter(
            id__in=user_ids,
            is_active=True,
            is_deleted=False,
            is_suspended=False,
            is_account_paused=False,
        )
        .filter(public_profile_filter)
        .select_related(
            "label",
            "member_profile",
            "guest_profile",
        )
        .distinct()
    )

    if boundary_excluded_ids:
        queryset = queryset.exclude(
            id__in=boundary_excluded_ids
        )

    return queryset.order_by(
        "name",
        "family",
        "username",
        "id",
    )
