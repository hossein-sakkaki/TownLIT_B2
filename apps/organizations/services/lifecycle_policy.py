# apps/organizations/services/lifecycle_policy.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-20.
# Last Update by Hossein Sakkaki on 2026-10-20.
#

from django.core.exceptions import PermissionDenied

from apps.organizations.constants import OrganizationStatus
from apps.organizations.models import Organization


def require_operational_organization(*, organization):
    """Serialize routine Settings writes with lifecycle transitions.

    Call within transaction.atomic(). Restorative Governance actions use
    their own restricted workflow and must not use this guard.
    """
    locked = (
        Organization.objects
        .select_for_update()
        .only("id", "status")
        .get(pk=organization.pk)
    )
    if locked.status != OrganizationStatus.ACTIVE:
        raise PermissionDenied(
            "Organization settings cannot be changed while the "
            "organization is suspended or closed."
        )
    return locked
