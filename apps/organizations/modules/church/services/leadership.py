# apps/organizations/modules/church/services/leadership.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.organizations.constants import OrganizationMembershipStatus
from apps.organizations.modules.church.constants import (
    ChurchAuditEvent,
    ChurchLeadershipAssignmentStatus,
    ChurchPermissionKey,
)
from apps.organizations.modules.church.models import ChurchLeadershipAssignment
from apps.organizations.modules.church.services.access import ensure_church_permission
from apps.organizations.modules.church.services.audit import record_church_audit


@transaction.atomic
def assign_church_leadership(
    *,
    workspace,
    membership,
    actor,
    position_type,
    custom_title=None,
    campus=None,
    ministry=None,
    publicly_listed=False,
    sort_order=100,
    started_at=None,
):
    ensure_church_permission(
        actor=actor,
        workspace=workspace,
        permission_key=ChurchPermissionKey.MANAGE_LEADERSHIP,
    )

    if membership.status != OrganizationMembershipStatus.ACTIVE:
        raise ValidationError(
            "Only active organization members can hold church leadership positions."
        )

    assignment = ChurchLeadershipAssignment(
        workspace=workspace,
        membership=membership,
        campus=campus,
        ministry=ministry,
        position_type=position_type,
        custom_title=custom_title,
        publicly_listed=publicly_listed,
        sort_order=sort_order,
        started_at=started_at or timezone.now(),
    )
    assignment.full_clean()
    assignment.save()

    record_church_audit(
        workspace=workspace,
        event=ChurchAuditEvent.LEADERSHIP_ASSIGNED,
        actor=actor,
        membership=membership,
        entity=assignment,
        metadata={
            "position_type": assignment.position_type,
            "title": assignment.effective_title,
        },
    )

    return assignment


@transaction.atomic
def end_church_leadership(*, assignment, actor, now=None):
    now = now or timezone.now()
    assignment = (
        ChurchLeadershipAssignment.objects
        .select_for_update()
        .select_related(
            "workspace__activation__organization",
            "membership__member__user",
        )
        .get(pk=assignment.pk)
    )

    ensure_church_permission(
        actor=actor,
        workspace=assignment.workspace,
        permission_key=ChurchPermissionKey.MANAGE_LEADERSHIP,
    )

    if assignment.status == ChurchLeadershipAssignmentStatus.ENDED:
        return assignment

    assignment.status = ChurchLeadershipAssignmentStatus.ENDED
    assignment.ended_at = now
    assignment.full_clean()
    assignment.save(
        update_fields=[
            "status",
            "ended_at",
            "updated_at",
        ]
    )

    record_church_audit(
        workspace=assignment.workspace,
        event=ChurchAuditEvent.LEADERSHIP_ENDED,
        actor=actor,
        membership=assignment.membership,
        entity=assignment,
        metadata={
            "position_type": assignment.position_type,
            "title": assignment.effective_title,
        },
    )

    return assignment
