# apps/organizations/modules/church/services/access.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from django.core.exceptions import PermissionDenied

from apps.organizations.constants import (
    OrganizationModuleAccessMode,
    OrganizationModuleKey,
    OrganizationPermissionKey,
    OrganizationRoleScope,
)
from apps.organizations.services.access import user_has_organization_permission
from apps.organizations.services.modules import get_organization_module_access


def user_has_church_permission(*, user, workspace, permission_key) -> bool:
    organization = workspace.activation.organization

    # Organization/module managers inherit operational access to the module.
    if user_has_organization_permission(
        user=user,
        organization=organization,
        permission_key=OrganizationPermissionKey.MANAGE_MODULES,
        scope_type=OrganizationRoleScope.MODULE,
        scope_key=OrganizationModuleKey.CHURCH,
    ):
        return True

    return user_has_organization_permission(
        user=user,
        organization=organization,
        permission_key=permission_key,
        scope_type=OrganizationRoleScope.MODULE,
        scope_key=OrganizationModuleKey.CHURCH,
    )


def ensure_church_module_access(*, workspace, require_write=True):
    module_access = get_organization_module_access(
        organization=workspace.activation.organization,
        module_key=OrganizationModuleKey.CHURCH,
        actor=None,
    )

    readable_modes = {
        OrganizationModuleAccessMode.FULL,
        OrganizationModuleAccessMode.READ_ONLY,
    }

    if module_access.access_mode not in readable_modes:
        raise PermissionDenied(
            f"Church module is unavailable: {module_access.reason}."
        )

    if require_write and module_access.access_mode != OrganizationModuleAccessMode.FULL:
        raise PermissionDenied(
            f"Church module is read-only: {module_access.reason}."
        )

    return module_access


def ensure_church_permission(
    *,
    actor,
    workspace,
    permission_key,
    require_write=True,
):
    module_access = ensure_church_module_access(
        workspace=workspace,
        require_write=require_write,
    )

    if not user_has_church_permission(
        user=actor,
        workspace=workspace,
        permission_key=permission_key,
    ):
        raise PermissionDenied(
            "You do not have permission to perform this Church module operation."
        )

    return module_access
