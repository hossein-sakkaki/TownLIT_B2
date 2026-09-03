# apps/organizations/modules/church/selectors/teaching.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-31.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from django.db.models import Q

from apps.organizations.constants import OrganizationMembershipStatus
from apps.organizations.models import OrganizationMembership
from apps.organizations.modules.church.constants import (
    ChurchPermissionKey,
    ChurchTeachingAudience,
    ChurchTeachingSeriesStatus,
    ChurchTeachingStatus,
)
from apps.organizations.modules.church.models import ChurchTeachingSeries
from apps.organizations.modules.church.services.access import (
    ensure_church_module_access,
    ensure_church_permission,
    user_has_church_permission,
)
from apps.posts.models.church_teaching import ChurchTeachingContent


def list_church_teaching_series(*, workspace, include_archived=False):
    """Return teaching series for one Church workspace."""

    queryset = (
        ChurchTeachingSeries.objects
        .filter(workspace=workspace)
        .select_related("campus", "ministry")
        .order_by("sort_order", "name", "id")
    )

    if not include_archived:
        queryset = queryset.exclude(
            status=ChurchTeachingSeriesStatus.ARCHIVED,
        )

    return queryset


def _is_authenticated(viewer) -> bool:
    return bool(
        viewer
        and getattr(viewer, "is_authenticated", False)
    )


def _has_teaching_staff_access(*, workspace, viewer) -> bool:
    if not _is_authenticated(viewer):
        return False

    for permission_key in (
        ChurchPermissionKey.VIEW_TEACHING,
        ChurchPermissionKey.MANAGE_TEACHING,
        ChurchPermissionKey.PUBLISH_TEACHING,
    ):
        if user_has_church_permission(
            user=viewer,
            workspace=workspace,
            permission_key=permission_key,
        ):
            return True

    return False


def _base_content_queryset(*, workspace):
    return (
        ChurchTeachingContent.objects
        .filter(workspace=workspace)
        .select_related(
            "workspace__activation__organization",
            "series",
            "campus",
            "ministry",
            "occurrence",
            "speaker_membership__member__user",
        )
        .prefetch_related("scripture_references")
    )


def list_visible_church_teaching_contents(
    *,
    workspace,
    viewer=None,
    include_manager_drafts=False,
):
    """Return Church teaching visible to the supplied viewer."""

    ensure_church_module_access(
        workspace=workspace,
        require_write=False,
    )

    queryset = _base_content_queryset(
        workspace=workspace,
    ).filter(
        is_active=True,
        is_suspended=False,
    )

    is_staff_viewer = _has_teaching_staff_access(
        workspace=workspace,
        viewer=viewer,
    )

    if include_manager_drafts and is_staff_viewer:
        return queryset.order_by(
            "-published_at",
            "-created_at",
            "-id",
        )

    queryset = queryset.filter(
        status=ChurchTeachingStatus.PUBLISHED,
    )

    if not _is_authenticated(viewer):
        return queryset.filter(
            audience=ChurchTeachingAudience.PUBLIC,
        ).order_by(
            "-published_at",
            "-id",
        )

    active_member = OrganizationMembership.objects.filter(
        organization=workspace.activation.organization,
        member__user=viewer,
        status=OrganizationMembershipStatus.ACTIVE,
    ).exists()

    visibility = Q(
        audience=ChurchTeachingAudience.PUBLIC,
    )

    if active_member:
        visibility |= Q(
            audience=ChurchTeachingAudience.ORGANIZATION_MEMBERS,
        )

    if is_staff_viewer:
        visibility |= Q(
            audience=ChurchTeachingAudience.INTERNAL,
        )

    return queryset.filter(
        visibility
    ).order_by(
        "-published_at",
        "-id",
    )


def list_manageable_church_teaching_contents(*, workspace, actor):
    """Return the full teaching management collection for authorized staff."""

    ensure_church_permission(
        actor=actor,
        workspace=workspace,
        permission_key=ChurchPermissionKey.MANAGE_TEACHING,
        require_write=False,
    )

    return _base_content_queryset(
        workspace=workspace,
    ).order_by(
        "-created_at",
        "-id",
    )
