# apps/organizations/selectors/organizations.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-29.
#

from django.db.models import Count, Q

from apps.organizations.constants import (
    OrganizationConnectionStatus,
    OrganizationConnectionType,
    OrganizationMembershipStatus,
    OrganizationStatus,
    OrganizationVisibility,
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
