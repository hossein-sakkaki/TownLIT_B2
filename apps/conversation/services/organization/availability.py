# apps/conversation/services/organization/availability.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from __future__ import annotations

from apps.organizations.constants import OrganizationStatus
from apps.organizations.selectors import is_organization_verified


def organization_messenger_is_available(organization, *, now=None) -> bool:
    return bool(
        organization
        and organization.status == OrganizationStatus.ACTIVE
        and is_organization_verified(
            organization=organization,
            now=now,
        )
    )
