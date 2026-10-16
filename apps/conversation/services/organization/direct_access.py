# apps/conversation/services/organization/direct_access.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from __future__ import annotations

from apps.organizations.constants import OrganizationPermissionKey
from apps.organizations.services.access import user_has_organization_permission_strict

from .availability import organization_messenger_is_available


VIEW_PERMISSION_KEYS = (
    OrganizationPermissionKey.VIEW_MESSENGER,
    OrganizationPermissionKey.MANAGE_MESSENGER,
)
REPLY_PERMISSION_KEYS = (
    OrganizationPermissionKey.REPLY_MESSENGER,
    OrganizationPermissionKey.MANAGE_MESSENGER,
)
ASSIGN_PERMISSION_KEYS = (
    OrganizationPermissionKey.ASSIGN_MESSENGER,
    OrganizationPermissionKey.MANAGE_MESSENGER,
)
MANAGE_PERMISSION_KEYS = (
    OrganizationPermissionKey.MANAGE_MESSENGER,
)


def organization_operator_has_any_permission(
    *,
    user,
    organization,
    permission_keys,
    now=None,
) -> bool:
    if not organization_messenger_is_available(organization, now=now):
        return False

    return any(
        user_has_organization_permission_strict(
            user=user,
            organization=organization,
            permission_key=permission_key,
            now=now,
        )
        for permission_key in permission_keys
    )


def organization_operator_can_view(*, user, organization, now=None) -> bool:
    return organization_operator_has_any_permission(
        user=user,
        organization=organization,
        permission_keys=VIEW_PERMISSION_KEYS,
        now=now,
    )


def organization_operator_can_reply(*, user, organization, now=None) -> bool:
    return organization_operator_has_any_permission(
        user=user,
        organization=organization,
        permission_keys=REPLY_PERMISSION_KEYS,
        now=now,
    )


def organization_operator_can_assign(*, user, organization, now=None) -> bool:
    return organization_operator_has_any_permission(
        user=user,
        organization=organization,
        permission_keys=ASSIGN_PERMISSION_KEYS,
        now=now,
    )


def organization_operator_can_manage(*, user, organization, now=None) -> bool:
    return organization_operator_has_any_permission(
        user=user,
        organization=organization,
        permission_keys=MANAGE_PERMISSION_KEYS,
        now=now,
    )
