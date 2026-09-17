# apps/organizations/modules/worship/services/availability.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-07.
#

from dataclasses import dataclass

from django.utils import timezone

from apps.organizations.constants import (
    OrganizationModuleActivationStatus,
    OrganizationStatus,
)
from apps.organizations.modules.worship.constants import (
    OrganizationMusicContributionStatus,
    OrganizationMusicLicenseStatus,
)
from apps.organizations.modules.worship.models import (
    OrganizationMusicContribution,
)


@dataclass(frozen=True)
class OrganizationMusicOriginAvailability:
    allowed: bool
    reason: str = ""


def validate_organization_music_origin(
    *,
    track,
    rights,
    contribution=None,
    at=None,
):
    now = at or timezone.now()

    if contribution is None:
        contribution = (
            OrganizationMusicContribution.objects
            .select_related(
                "license",
                "workspace__activation__organization",
            )
            .filter(track=track)
            .first()
        )

    if contribution is None:
        return OrganizationMusicOriginAvailability(
            False,
            "Organization music contribution is unavailable.",
        )

    if contribution.track_id != track.id:
        return OrganizationMusicOriginAvailability(
            False,
            "Organization music contribution does not match the track.",
        )

    if contribution.rights_record_id != rights.id:
        return OrganizationMusicOriginAvailability(
            False,
            "Organization music rights record does not match the contribution.",
        )

    if contribution.status != OrganizationMusicContributionStatus.PUBLISHED:
        return OrganizationMusicOriginAvailability(
            False,
            "Organization music contribution is not published.",
        )

    license = contribution.license

    if license.workspace_id != contribution.workspace_id:
        return OrganizationMusicOriginAvailability(
            False,
            "Organization music license does not belong to the contribution workspace.",
        )

    if license.status != OrganizationMusicLicenseStatus.ACTIVE:
        return OrganizationMusicOriginAvailability(
            False,
            "Organization music license is not active.",
        )

    if license.effective_from and license.effective_from > now:
        return OrganizationMusicOriginAvailability(
            False,
            "Organization music license is not active yet.",
        )

    if license.effective_until and license.effective_until <= now:
        return OrganizationMusicOriginAvailability(
            False,
            "Organization music license has expired.",
        )

    activation = contribution.workspace.activation
    organization = activation.organization

    if organization.status != OrganizationStatus.ACTIVE:
        return OrganizationMusicOriginAvailability(
            False,
            "Organization is unavailable.",
        )

    if activation.status != OrganizationModuleActivationStatus.ENABLED:
        return OrganizationMusicOriginAvailability(
            False,
            "Worship module activation is unavailable.",
        )

    return OrganizationMusicOriginAvailability(True)