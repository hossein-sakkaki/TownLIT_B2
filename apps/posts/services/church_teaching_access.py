# apps/posts/services/church_teaching_access.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-31.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from django.core.exceptions import PermissionDenied

from apps.organizations.constants import OrganizationMembershipStatus
from apps.organizations.models import OrganizationMembership
from apps.organizations.modules.church.constants import (
    ChurchPermissionKey,
    ChurchTeachingAudience,
    ChurchTeachingStatus,
)
from apps.organizations.modules.church.services.access import (
    ensure_church_module_access,
    user_has_church_permission,
)


def _is_authenticated(viewer) -> bool:
    return bool(
        viewer
        and getattr(viewer, "is_authenticated", False)
    )


def _module_is_readable(workspace) -> bool:
    try:
        ensure_church_module_access(
            workspace=workspace,
            require_write=False,
        )
        return True
    except PermissionDenied:
        return False


def _is_active_organization_member(*, content, viewer) -> bool:
    if not _is_authenticated(viewer):
        return False

    return OrganizationMembership.objects.filter(
        organization=content.workspace.activation.organization,
        member__user=viewer,
        status=OrganizationMembershipStatus.ACTIVE,
    ).exists()


def _has_teaching_staff_access(*, content, viewer) -> bool:
    if not _is_authenticated(viewer):
        return False

    if not _module_is_readable(content.workspace):
        return False

    for permission_key in (
        ChurchPermissionKey.VIEW_TEACHING,
        ChurchPermissionKey.MANAGE_TEACHING,
        ChurchPermissionKey.PUBLISH_TEACHING,
    ):
        if user_has_church_permission(
            user=viewer,
            workspace=content.workspace,
            permission_key=permission_key,
        ):
            return True

    return False


def can_view_church_teaching_content(
    *,
    content,
    viewer,
    include_manager_preview: bool = False,
) -> bool:
    """Authorize Church teaching visibility without profile-policy coupling."""

    if not getattr(content, "is_active", False):
        return False

    if getattr(content, "is_suspended", False):
        return False

    if include_manager_preview and _has_teaching_staff_access(
        content=content,
        viewer=viewer,
    ):
        return True

    if content.status != ChurchTeachingStatus.PUBLISHED:
        return False

    if not _module_is_readable(content.workspace):
        return False

    if content.audience == ChurchTeachingAudience.PUBLIC:
        return True

    if content.audience == ChurchTeachingAudience.ORGANIZATION_MEMBERS:
        return _is_active_organization_member(
            content=content,
            viewer=viewer,
        )

    if content.audience == ChurchTeachingAudience.INTERNAL:
        return _has_teaching_staff_access(
            content=content,
            viewer=viewer,
        )

    return False
