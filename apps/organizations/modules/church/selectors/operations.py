# apps/organizations/modules/church/selectors/operations.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-31.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from apps.organizations.constants import OrganizationMembershipStatus
from apps.organizations.modules.church.constants import (
    ChurchResourceReservationStatus,
    ChurchResourceStatus,
    ChurchServicePlanStatus,
    ChurchServingAssignmentStatus,
    ChurchServingTeamMembershipStatus,
    ChurchServingTeamStatus,
)
from apps.organizations.modules.church.models import (
    ChurchResource,
    ChurchResourceReservation,
    ChurchServicePlan,
    ChurchServingAssignment,
    ChurchServingTeam,
    ChurchServingTeamMembership,
)


def list_active_church_serving_teams(*, workspace):
    return (
        ChurchServingTeam.objects
        .filter(
            workspace=workspace,
            status=ChurchServingTeamStatus.ACTIVE,
        )
        .select_related("campus", "ministry")
        .order_by("sort_order", "name", "id")
    )


def list_active_church_serving_team_members(*, team):
    return (
        ChurchServingTeamMembership.objects
        .filter(
            team=team,
            status=ChurchServingTeamMembershipStatus.ACTIVE,
            membership__status=OrganizationMembershipStatus.ACTIVE,
        )
        .select_related("membership__member__user")
        .order_by("-is_team_lead", "joined_at", "id")
    )


def get_church_service_plan_for_occurrence(*, occurrence):
    return (
        ChurchServicePlan.objects
        .filter(occurrence=occurrence)
        .prefetch_related("items", "serving_assignments")
        .first()
    )


def list_member_church_serving_assignments(*, membership, include_closed=False):
    qs = (
        ChurchServingAssignment.objects
        .filter(membership=membership)
        .select_related(
            "service_plan__occurrence",
            "service_plan__workspace",
            "team",
        )
        .order_by("service_plan__occurrence__starts_at", "id")
    )

    if not include_closed:
        qs = qs.exclude(
            status__in={
                ChurchServingAssignmentStatus.CANCELED,
                ChurchServingAssignmentStatus.COMPLETED,
            }
        )

    return qs


def list_active_church_resources(*, workspace):
    return (
        ChurchResource.objects
        .filter(
            workspace=workspace,
            status=ChurchResourceStatus.ACTIVE,
        )
        .select_related("campus", "ministry")
        .order_by("sort_order", "name", "id")
    )


def list_church_resource_reservations(*, resource, include_closed=False):
    qs = (
        ChurchResourceReservation.objects
        .filter(resource=resource)
        .select_related("occurrence")
        .order_by("starts_at", "id")
    )

    if not include_closed:
        qs = qs.filter(status=ChurchResourceReservationStatus.RESERVED)

    return qs


def list_open_church_service_plans(*, workspace):
    return (
        ChurchServicePlan.objects
        .filter(
            workspace=workspace,
            status__in={
                ChurchServicePlanStatus.DRAFT,
                ChurchServicePlanStatus.PUBLISHED,
            },
        )
        .select_related("occurrence")
        .order_by("occurrence__starts_at", "id")
    )
