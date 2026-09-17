# apps/organizations/modules/worship/services/access.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-07.
#

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.utils import timezone

from apps.organizations.constants import (
    OrganizationMembershipStatus,
    OrganizationModuleAccessMode,
    OrganizationModuleKey,
    OrganizationRoleScope,
)
from apps.organizations.models import OrganizationMembership
from apps.organizations.modules.worship.constants import WorshipPermissionKey
from apps.organizations.services.access import user_has_organization_permission
from apps.organizations.services.modules import get_organization_module_access


_DIRECT_LEGAL_PERMISSIONS = {
    WorshipPermissionKey.MANAGE_RIGHTS,
    WorshipPermissionKey.MANAGE_LICENSES,
}


def get_active_worship_membership_for_user(*, workspace, user):
    if not user or not getattr(user, "is_authenticated", False):
        return None

    return (
        OrganizationMembership.objects
        .select_related(
            "member__user",
            "organization",
        )
        .filter(
            organization=workspace.activation.organization,
            member__user=user,
            status=OrganizationMembershipStatus.ACTIVE,
        )
        .first()
    )


def user_has_direct_worship_permission(
    *,
    user,
    workspace,
    permission_key,
    now=None,
) -> bool:
    """
    Resolve sensitive Worship permissions without platform bypass.
    """

    membership = get_active_worship_membership_for_user(
        workspace=workspace,
        user=user,
    )

    if not membership:
        return False

    now = now or timezone.now()

    return (
        membership.role_assignments
        .filter(
            is_active=True,
            revoked_at__isnull=True,
            starts_at__lte=now,
            role__is_active=True,
            role__role_permissions__permission__key=permission_key,
            role__role_permissions__permission__is_active=True,
        )
        .filter(
            Q(ends_at__isnull=True)
            | Q(ends_at__gt=now)
        )
        .filter(
            Q(
                scope_type=OrganizationRoleScope.ORGANIZATION,
                scope_key="",
            )
            | Q(
                scope_type=OrganizationRoleScope.MODULE,
                scope_key=OrganizationModuleKey.WORSHIP,
            )
        )
        .exists()
    )


def user_has_worship_permission(
    *,
    user,
    workspace,
    permission_key,
) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False

    if permission_key in _DIRECT_LEGAL_PERMISSIONS:
        return user_has_direct_worship_permission(
            user=user,
            workspace=workspace,
            permission_key=permission_key,
        )

    return user_has_organization_permission(
        user=user,
        organization=workspace.activation.organization,
        permission_key=permission_key,
        scope_type=OrganizationRoleScope.MODULE,
        scope_key=OrganizationModuleKey.WORSHIP,
    )


def ensure_worship_permission(
    *,
    actor,
    workspace,
    permission_key,
    require_write=True,
):
    access = get_organization_module_access(
        organization=workspace.activation.organization,
        module_key=OrganizationModuleKey.WORSHIP,
        actor=None,
    )

    readable_modes = {
        OrganizationModuleAccessMode.FULL,
        OrganizationModuleAccessMode.READ_ONLY,
    }

    if access.access_mode not in readable_modes:
        raise PermissionDenied(
            f"Worship module is unavailable: {access.reason}."
        )

    if require_write and access.access_mode != OrganizationModuleAccessMode.FULL:
        raise PermissionDenied(
            f"Worship module is read-only: {access.reason}."
        )

    if not user_has_worship_permission(
        user=actor,
        workspace=workspace,
        permission_key=permission_key,
    ):
        if permission_key in _DIRECT_LEGAL_PERMISSIONS:
            raise PermissionDenied(
                "Worship legal rights management requires an explicit Organization Worship role permission."
            )

        raise PermissionDenied(
            "You do not have permission to perform this Worship module operation."
        )

    return access