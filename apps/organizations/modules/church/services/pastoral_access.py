# apps/organizations/modules/church/services/pastoral_access.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-31.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.utils import timezone

from apps.organizations.constants import (
    ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES,
    OrganizationModuleKey,
    OrganizationRoleScope,
)
from apps.organizations.modules.church.constants import (
    ChurchPastoralCareAssignmentStatus,
    ChurchPastoralCareNoteVisibility,
    ChurchPastoralCareSensitivity,
    ChurchPermissionKey,
)
from apps.organizations.modules.church.services.access import ensure_church_module_access
from apps.organizations.models import OrganizationMembership


def get_active_pastoral_membership_for_user(*, workspace, user):
    if not user or not getattr(user, "is_authenticated", False):
        return None

    return (
        OrganizationMembership.objects
        .select_related("member__user", "organization")
        .filter(
            organization=workspace.activation.organization,
            member__user=user,
            status__in=ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES,
        )
        .first()
    )


def user_has_direct_church_permission(*, user, workspace, permission_key, now=None) -> bool:
    """
    Sensitive Church permissions intentionally do not inherit from:
    - platform is_staff
    - generic organizations.modules.manage

    Pastoral care requires an explicit Church role permission assignment.
    """
    membership = get_active_pastoral_membership_for_user(workspace=workspace, user=user)
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
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))
        .filter(
            Q(scope_type=OrganizationRoleScope.ORGANIZATION, scope_key="")
            | Q(scope_type=OrganizationRoleScope.MODULE, scope_key=OrganizationModuleKey.CHURCH)
        )
        .exists()
    )


def user_is_active_pastoral_case_assignee(*, user, care_case) -> bool:
    membership = get_active_pastoral_membership_for_user(
        workspace=care_case.workspace,
        user=user,
    )
    if not membership:
        return False

    return care_case.assignments.filter(
        membership=membership,
        status=ChurchPastoralCareAssignmentStatus.ACTIVE,
    ).exists()


def can_view_pastoral_case(*, user, care_case) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False

    if user_has_direct_church_permission(
        user=user,
        workspace=care_case.workspace,
        permission_key=ChurchPermissionKey.MANAGE_PASTORAL_CARE,
    ):
        return True

    # An explicit active case assignment grants case-level access
    # regardless of sensitivity. It does not grant global pastoral access.
    if user_is_active_pastoral_case_assignee(
        user=user,
        care_case=care_case,
    ):
        return True

    if care_case.sensitivity == ChurchPastoralCareSensitivity.STANDARD:
        return user_has_direct_church_permission(
            user=user,
            workspace=care_case.workspace,
            permission_key=ChurchPermissionKey.VIEW_PASTORAL_CARE,
        )

    return user_has_direct_church_permission(
        user=user,
        workspace=care_case.workspace,
        permission_key=ChurchPermissionKey.VIEW_CONFIDENTIAL_PASTORAL_CARE,
    )


def can_view_pastoral_note(*, user, note) -> bool:
    if not can_view_pastoral_case(user=user, care_case=note.case):
        return False

    if note.visibility == ChurchPastoralCareNoteVisibility.PASTORAL_LEADERS:
        return user_has_direct_church_permission(
            user=user,
            workspace=note.case.workspace,
            permission_key=ChurchPermissionKey.VIEW_CONFIDENTIAL_PASTORAL_CARE,
        ) or user_has_direct_church_permission(
            user=user,
            workspace=note.case.workspace,
            permission_key=ChurchPermissionKey.MANAGE_PASTORAL_CARE,
        )

    return user_is_active_pastoral_case_assignee(user=user, care_case=note.case) or user_has_direct_church_permission(
        user=user,
        workspace=note.case.workspace,
        permission_key=ChurchPermissionKey.VIEW_CONFIDENTIAL_PASTORAL_CARE,
    ) or user_has_direct_church_permission(
        user=user,
        workspace=note.case.workspace,
        permission_key=ChurchPermissionKey.MANAGE_PASTORAL_CARE,
    )


def ensure_pastoral_manage_permission(*, actor, workspace, require_write=True):
    ensure_church_module_access(workspace=workspace, require_write=require_write)
    if not user_has_direct_church_permission(
        user=actor,
        workspace=workspace,
        permission_key=ChurchPermissionKey.MANAGE_PASTORAL_CARE,
    ):
        raise PermissionDenied(
            "Pastoral care management requires an explicit confidential Church role permission."
        )


def ensure_pastoral_case_access(*, actor, care_case, require_write=False):
    ensure_church_module_access(workspace=care_case.workspace, require_write=require_write)
    if not can_view_pastoral_case(user=actor, care_case=care_case):
        raise PermissionDenied("You do not have access to this pastoral care case.")
