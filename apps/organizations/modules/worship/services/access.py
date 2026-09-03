# apps/organizations/modules/worship/services/access.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from django.core.exceptions import PermissionDenied

from apps.organizations.constants import OrganizationModuleAccessMode, OrganizationModuleKey, OrganizationRoleScope
from apps.organizations.services.access import user_has_organization_permission
from apps.organizations.services.modules import get_organization_module_access


def user_has_worship_permission(*, user, workspace, permission_key) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return user_has_organization_permission(
        user=user,
        organization=workspace.activation.organization,
        permission_key=permission_key,
        scope_type=OrganizationRoleScope.MODULE,
        scope_key=OrganizationModuleKey.WORSHIP,
    )


def ensure_worship_permission(*, actor, workspace, permission_key, require_write=True):
    access = get_organization_module_access(
        organization=workspace.activation.organization,
        module_key=OrganizationModuleKey.WORSHIP,
        actor=None,
    )
    if access.access_mode not in {OrganizationModuleAccessMode.FULL, OrganizationModuleAccessMode.READ_ONLY}:
        raise PermissionDenied(f"Worship module is unavailable: {access.reason}.")
    if require_write and access.access_mode != OrganizationModuleAccessMode.FULL:
        raise PermissionDenied(f"Worship module is read-only: {access.reason}.")
    if not user_has_worship_permission(user=actor, workspace=workspace, permission_key=permission_key):
        raise PermissionDenied("You do not have permission to perform this Worship module operation.")
    return access
