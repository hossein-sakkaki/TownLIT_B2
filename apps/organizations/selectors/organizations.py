# apps/organizations/selectors/organizations.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-09-13.
#

from django.db.models import Count, Q

from apps.organizations.constants import (
    CURRENT_MEMBERSHIP_STATUSES,
    OrganizationConnectionStatus,
    OrganizationConnectionType,
    OrganizationMembershipStatus,
    OrganizationStatus,
    OrganizationVisibility,
)
from apps.organizations.feature_flags import (
    organizations_enabled,
)
from apps.organizations.models import Organization


def public_organizations_queryset():
    return (
        Organization.objects
        .filter(
            status=OrganizationStatus.ACTIVE,
            visibility=OrganizationVisibility.PUBLIC,
        )
        .annotate(
            follower_count=Count(
                "connections",
                filter=Q(
                    connections__status=(
                        OrganizationConnectionStatus.ACTIVE
                    ),
                    connections__relationship_type=(
                        OrganizationConnectionType.FOLLOWER
                    ),
                ),
                distinct=True,
            ),
            member_count=Count(
                "memberships",
                filter=Q(
                    memberships__status=(
                        OrganizationMembershipStatus.ACTIVE
                    ),
                ),
                distinct=True,
            ),
        )
    )


def current_organizations_for_member(*, member):
    if not organizations_enabled():
        return Organization.objects.none()

    return (
        Organization.objects
        .filter(
            memberships__member=member,
            memberships__status__in=(
                CURRENT_MEMBERSHIP_STATUSES
            ),
        )
        .distinct()
        .order_by(
            "name",
            "id",
        )
    )


def public_organizations_for_member(*, member):
    if not organizations_enabled():
        return Organization.objects.none()

    return (
        Organization.objects
        .filter(
            status=OrganizationStatus.ACTIVE,
            visibility=OrganizationVisibility.PUBLIC,
            memberships__member=member,
            memberships__status=(
                OrganizationMembershipStatus.ACTIVE
            ),
        )
        .distinct()
        .order_by(
            "name",
            "id",
        )
    )