# apps/posts/services/organization_access.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-14.
# Last Update by Hossein Sakkaki on 2026-09-14.
#

from apps.organizations.constants import (
    OrganizationPermissionKey,
)
from apps.organizations.services.access import (
    user_has_organization_permission,
)


def can_manage_organization_content(
    *,
    user,
    organization,
) -> bool:
    return user_has_organization_permission(
        user=user,
        organization=organization,
        permission_key=(
            OrganizationPermissionKey.MANAGE_CONTENT
        ),
    )