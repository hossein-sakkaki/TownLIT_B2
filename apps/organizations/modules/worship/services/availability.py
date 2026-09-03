# apps/organizations/modules/worship/services/availability.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from dataclasses import dataclass

from django.utils import timezone

from apps.organizations.constants import OrganizationModuleActivationStatus, OrganizationStatus
from apps.organizations.modules.worship.constants import OrganizationMusicContributionStatus, OrganizationMusicLicenseStatus
from apps.organizations.modules.worship.models import OrganizationMusicContribution


@dataclass(frozen=True)
class OrganizationMusicOriginAvailability:
    allowed: bool
    reason: str = ""


def validate_organization_music_origin(*, track, rights, origin, at=None):
    now = at or timezone.now()
    contribution_id = str(origin.get("contribution_public_id") or "").strip()
    license_id = str(origin.get("license_public_id") or "").strip()
    if not contribution_id or not license_id:
        return OrganizationMusicOriginAvailability(False, "Organization music origin is incomplete.")
    try:
        contribution = OrganizationMusicContribution.objects.select_related("license", "workspace__activation__organization").get(public_id=contribution_id, track=track, rights_record=rights)
    except Exception:
        return OrganizationMusicOriginAvailability(False, "Organization music contribution is unavailable.")
    if contribution.status != OrganizationMusicContributionStatus.PUBLISHED:
        return OrganizationMusicOriginAvailability(False, "Organization music contribution is not published.")
    license = contribution.license
    if str(license.public_id) != license_id or license.status != OrganizationMusicLicenseStatus.ACTIVE:
        return OrganizationMusicOriginAvailability(False, "Organization music license is not active.")
    if license.effective_from and license.effective_from > now:
        return OrganizationMusicOriginAvailability(False, "Organization music license is not active yet.")
    if license.effective_until and license.effective_until <= now:
        return OrganizationMusicOriginAvailability(False, "Organization music license has expired.")
    activation = contribution.workspace.activation
    if activation.organization.status != OrganizationStatus.ACTIVE:
        return OrganizationMusicOriginAvailability(False, "Organization is unavailable.")
    if activation.status != OrganizationModuleActivationStatus.ENABLED:
        return OrganizationMusicOriginAvailability(False, "Worship module activation is unavailable.")
    return OrganizationMusicOriginAvailability(True)
