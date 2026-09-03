# apps/organizations/modules/church/selectors/pastoral_care.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-31.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from django.db.models import Q

from apps.organizations.modules.church.constants import (
    ChurchPastoralCareAssignmentStatus,
    ChurchPastoralCareSensitivity,
    ChurchPermissionKey,
)
from apps.organizations.modules.church.models import ChurchPastoralCareCase, ChurchPastoralCareNote
from apps.organizations.modules.church.services.pastoral_access import (
    get_active_pastoral_membership_for_user,
    user_has_direct_church_permission,
)


def list_pastoral_care_cases_for_actor(*, workspace, actor):
    membership = get_active_pastoral_membership_for_user(workspace=workspace, user=actor)
    if not membership:
        return ChurchPastoralCareCase.objects.none()

    base = (
        ChurchPastoralCareCase.objects
        .select_related("congregant", "congregant__member__user", "congregant__guest_profile__user")
        .filter(workspace=workspace)
    )

    if user_has_direct_church_permission(
        user=actor,
        workspace=workspace,
        permission_key=ChurchPermissionKey.MANAGE_PASTORAL_CARE,
    ) or user_has_direct_church_permission(
        user=actor,
        workspace=workspace,
        permission_key=ChurchPermissionKey.VIEW_CONFIDENTIAL_PASTORAL_CARE,
    ):
        return base

    if user_has_direct_church_permission(
        user=actor,
        workspace=workspace,
        permission_key=ChurchPermissionKey.VIEW_PASTORAL_CARE,
    ):
        return base.filter(
            Q(sensitivity=ChurchPastoralCareSensitivity.STANDARD)
            | Q(
                assignments__membership=membership,
                assignments__status=ChurchPastoralCareAssignmentStatus.ACTIVE,
            )
        ).distinct()

    return base.filter(
        assignments__membership=membership,
        assignments__status=ChurchPastoralCareAssignmentStatus.ACTIVE,
    ).distinct()


def list_pastoral_care_notes_for_actor(*, care_case, actor):
    from apps.organizations.modules.church.services.pastoral_access import can_view_pastoral_note

    notes = ChurchPastoralCareNote.objects.filter(case=care_case).select_related("author_membership__member__user")
    visible_ids = [note.id for note in notes if can_view_pastoral_note(user=actor, note=note)]
    return notes.filter(id__in=visible_ids)
