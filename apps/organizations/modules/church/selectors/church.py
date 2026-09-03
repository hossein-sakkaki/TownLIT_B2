# apps/organizations/modules/church/selectors/church.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from django.utils import timezone

from apps.organizations.constants import OrganizationModuleKey
from apps.organizations.modules.church.constants import (
    ChurchCampusStatus,
    ChurchGatheringOccurrenceStatus,
    ChurchLeadershipAssignmentStatus,
    ChurchMinistryStatus,
)
from apps.organizations.modules.church.models import ChurchWorkspace


def get_church_workspace(*, organization):
    return (
        ChurchWorkspace.objects
        .select_related(
            "activation__organization",
            "activation__module",
        )
        .filter(
            activation__organization=organization,
            activation__module__key=OrganizationModuleKey.CHURCH,
        )
        .first()
    )


def list_active_church_campuses(*, workspace):
    return workspace.campuses.filter(
        status=ChurchCampusStatus.ACTIVE,
    ).select_related("address")


def list_active_church_ministries(*, workspace):
    return workspace.ministries.filter(
        status=ChurchMinistryStatus.ACTIVE,
    ).select_related("campus")


def list_current_church_leadership(*, workspace, publicly_listed=None):
    queryset = (
        workspace.leadership_assignments
        .filter(status=ChurchLeadershipAssignmentStatus.ACTIVE)
        .select_related(
            "membership__member__user",
            "campus",
            "ministry",
        )
    )

    if publicly_listed is not None:
        queryset = queryset.filter(publicly_listed=publicly_listed)

    return queryset


def list_upcoming_church_gatherings(*, workspace, now=None):
    now = now or timezone.now()
    return (
        workspace.gathering_occurrences
        .filter(
            status=ChurchGatheringOccurrenceStatus.SCHEDULED,
            ends_at__gt=now,
        )
        .select_related("campus", "ministry", "series")
        .order_by("starts_at", "id")
    )
