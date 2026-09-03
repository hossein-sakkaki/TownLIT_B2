# apps/organizations/modules/church/services/serving_assignments.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-31.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.organizations.constants import OrganizationMembershipStatus
from apps.organizations.modules.church.constants import (
    ChurchAuditEvent,
    ChurchPermissionKey,
    ChurchServicePlanStatus,
    ChurchServingAssignmentStatus,
)
from apps.organizations.modules.church.models import ChurchServingAssignment
from apps.organizations.modules.church.services.access import (
    ensure_church_module_access,
    ensure_church_permission,
    user_has_church_permission,
)
from apps.organizations.modules.church.services.audit import record_church_audit


def _is_assignment_member(*, actor, assignment) -> bool:
    if not actor or not getattr(actor, "is_authenticated", False):
        return False

    try:
        return assignment.membership.member.user_id == actor.id
    except Exception:
        return False


def _ensure_assignment_actor(*, actor, assignment):
    if _is_assignment_member(actor=actor, assignment=assignment):
        return

    if user_has_church_permission(
        user=actor,
        workspace=assignment.service_plan.workspace,
        permission_key=ChurchPermissionKey.MANAGE_SERVING_ASSIGNMENTS,
    ):
        return

    raise PermissionDenied(
        "Only the assigned member or a Church serving manager can perform this action."
    )


@transaction.atomic
def create_church_serving_assignment(
    *,
    service_plan,
    membership,
    actor,
    role_label,
    team=None,
    notes=None,
    now=None,
):
    now = now or timezone.now()
    service_plan = (
        service_plan.__class__.objects
        .select_for_update()
        .select_related("workspace__activation__organization")
        .get(pk=service_plan.pk)
    )

    ensure_church_permission(
        actor=actor,
        workspace=service_plan.workspace,
        permission_key=ChurchPermissionKey.MANAGE_SERVING_ASSIGNMENTS,
    )

    if service_plan.status in {
        ChurchServicePlanStatus.COMPLETED,
        ChurchServicePlanStatus.CANCELED,
    }:
        raise ValidationError("Serving assignments cannot be added to a closed service plan.")

    if membership.status != OrganizationMembershipStatus.ACTIVE:
        raise ValidationError(
            "Only active organization members can receive Church serving assignments."
        )

    assignment = ChurchServingAssignment(
        service_plan=service_plan,
        membership=membership,
        team=team,
        role_label=role_label,
        status=ChurchServingAssignmentStatus.INVITED,
        invited_at=now,
        invited_by=actor,
        notes=notes,
    )

    # Resolve the idempotency key before uniqueness validation.
    assignment._sync_context_key()

    existing = (
        ChurchServingAssignment.objects
        .select_for_update()
        .filter(
            service_plan=service_plan,
            membership=membership,
            context_key=assignment.context_key,
        )
        .first()
    )

    if existing:
        if existing.status == ChurchServingAssignmentStatus.CANCELED:
            existing.status = ChurchServingAssignmentStatus.INVITED
            existing.invited_at = now
            existing.invited_by = actor
            existing.responded_at = None
            existing.canceled_at = None
            existing.canceled_by = None
            existing.checked_in_at = None
            existing.checked_out_at = None
            existing.completed_at = None
            existing.completed_by = None
            existing.notes = notes
            existing.full_clean()
            existing.save()
        return existing

    assignment.full_clean()
    assignment.save()

    record_church_audit(
        workspace=service_plan.workspace,
        event=ChurchAuditEvent.SERVING_ASSIGNMENT_CREATED,
        actor=actor,
        membership=membership,
        entity=assignment,
        metadata={
            "service_plan_public_id": str(service_plan.public_id),
            "team_public_id": str(team.public_id) if team else None,
            "role_label": assignment.role_label,
        },
    )

    return assignment


@transaction.atomic
def respond_to_church_serving_assignment(*, assignment, actor, accepted, now=None):
    now = now or timezone.now()
    assignment = (
        ChurchServingAssignment.objects
        .select_for_update()
        .select_related(
            "service_plan__workspace__activation__organization",
            "membership__member__user",
        )
        .get(pk=assignment.pk)
    )

    ensure_church_module_access(
        workspace=assignment.service_plan.workspace,
        require_write=True,
    )

    if not _is_assignment_member(actor=actor, assignment=assignment):
        raise PermissionDenied("Only the assigned member can respond to this serving invitation.")

    if assignment.membership.status != OrganizationMembershipStatus.ACTIVE:
        raise ValidationError("Inactive organization members cannot respond to serving assignments.")

    if assignment.status == ChurchServingAssignmentStatus.CANCELED:
        raise ValidationError("Canceled serving assignments cannot be accepted or declined.")

    if assignment.status == ChurchServingAssignmentStatus.COMPLETED:
        return assignment

    assignment.status = (
        ChurchServingAssignmentStatus.CONFIRMED
        if accepted
        else ChurchServingAssignmentStatus.DECLINED
    )
    assignment.responded_at = now
    assignment.checked_in_at = None
    assignment.checked_out_at = None
    assignment.completed_at = None
    assignment.completed_by = None
    assignment.full_clean()
    assignment.save()

    record_church_audit(
        workspace=assignment.service_plan.workspace,
        event=ChurchAuditEvent.SERVING_ASSIGNMENT_RESPONDED,
        actor=actor,
        membership=assignment.membership,
        entity=assignment,
        metadata={"status": assignment.status},
    )

    return assignment


@transaction.atomic
def check_in_church_serving_assignment(*, assignment, actor, now=None):
    now = now or timezone.now()
    assignment = (
        ChurchServingAssignment.objects
        .select_for_update()
        .select_related(
            "service_plan__workspace__activation__organization",
            "membership__member__user",
        )
        .get(pk=assignment.pk)
    )

    ensure_church_module_access(
        workspace=assignment.service_plan.workspace,
        require_write=True,
    )
    _ensure_assignment_actor(actor=actor, assignment=assignment)

    if assignment.status != ChurchServingAssignmentStatus.CONFIRMED:
        raise ValidationError("Only confirmed serving assignments can be checked in.")

    if assignment.checked_in_at:
        return assignment

    assignment.checked_in_at = now
    assignment.full_clean()
    assignment.save(update_fields=["checked_in_at", "updated_at"])

    record_church_audit(
        workspace=assignment.service_plan.workspace,
        event=ChurchAuditEvent.SERVING_ASSIGNMENT_CHECKED_IN,
        actor=actor,
        membership=assignment.membership,
        entity=assignment,
    )

    return assignment


@transaction.atomic
def check_out_church_serving_assignment(*, assignment, actor, now=None):
    now = now or timezone.now()
    assignment = (
        ChurchServingAssignment.objects
        .select_for_update()
        .select_related(
            "service_plan__workspace__activation__organization",
            "membership__member__user",
        )
        .get(pk=assignment.pk)
    )

    ensure_church_module_access(
        workspace=assignment.service_plan.workspace,
        require_write=True,
    )
    _ensure_assignment_actor(actor=actor, assignment=assignment)

    if not assignment.checked_in_at:
        raise ValidationError("Serving checkout requires a prior check-in.")
    if assignment.checked_out_at:
        return assignment
    if now <= assignment.checked_in_at:
        raise ValidationError("Serving checkout must occur after check-in.")

    assignment.checked_out_at = now
    assignment.full_clean()
    assignment.save(update_fields=["checked_out_at", "updated_at"])

    record_church_audit(
        workspace=assignment.service_plan.workspace,
        event=ChurchAuditEvent.SERVING_ASSIGNMENT_CHECKED_OUT,
        actor=actor,
        membership=assignment.membership,
        entity=assignment,
    )

    return assignment


@transaction.atomic
def cancel_church_serving_assignment(*, assignment, actor, now=None):
    now = now or timezone.now()
    assignment = (
        ChurchServingAssignment.objects
        .select_for_update()
        .select_related("service_plan__workspace__activation__organization", "membership")
        .get(pk=assignment.pk)
    )

    ensure_church_permission(
        actor=actor,
        workspace=assignment.service_plan.workspace,
        permission_key=ChurchPermissionKey.MANAGE_SERVING_ASSIGNMENTS,
    )

    if assignment.status == ChurchServingAssignmentStatus.CANCELED:
        return assignment
    if assignment.status == ChurchServingAssignmentStatus.COMPLETED:
        raise ValidationError("Completed serving assignments cannot be canceled.")
    if assignment.checked_in_at:
        raise ValidationError(
            "Checked-in serving assignments must be completed instead of canceled."
        )

    assignment.status = ChurchServingAssignmentStatus.CANCELED
    assignment.canceled_at = now
    assignment.canceled_by = actor
    assignment.full_clean()
    assignment.save(
        update_fields=["status", "canceled_at", "canceled_by", "updated_at"]
    )

    record_church_audit(
        workspace=assignment.service_plan.workspace,
        event=ChurchAuditEvent.SERVING_ASSIGNMENT_CANCELED,
        actor=actor,
        membership=assignment.membership,
        entity=assignment,
    )

    return assignment


@transaction.atomic
def complete_church_serving_assignment(*, assignment, actor, now=None):
    now = now or timezone.now()
    assignment = (
        ChurchServingAssignment.objects
        .select_for_update()
        .select_related("service_plan__workspace__activation__organization", "membership")
        .get(pk=assignment.pk)
    )

    ensure_church_permission(
        actor=actor,
        workspace=assignment.service_plan.workspace,
        permission_key=ChurchPermissionKey.MANAGE_SERVING_ASSIGNMENTS,
    )

    if assignment.status == ChurchServingAssignmentStatus.COMPLETED:
        return assignment
    if assignment.status != ChurchServingAssignmentStatus.CONFIRMED:
        raise ValidationError("Only confirmed serving assignments can be completed.")
    if not assignment.checked_in_at:
        raise ValidationError("Serving assignments must be checked in before completion.")

    if not assignment.checked_out_at:
        if now <= assignment.checked_in_at:
            raise ValidationError("Serving completion must occur after check-in.")
        assignment.checked_out_at = now

    assignment.status = ChurchServingAssignmentStatus.COMPLETED
    assignment.completed_at = now
    assignment.completed_by = actor
    assignment.full_clean()
    assignment.save(
        update_fields=[
            "status",
            "checked_out_at",
            "completed_at",
            "completed_by",
            "updated_at",
        ]
    )

    record_church_audit(
        workspace=assignment.service_plan.workspace,
        event=ChurchAuditEvent.SERVING_ASSIGNMENT_COMPLETED,
        actor=actor,
        membership=assignment.membership,
        entity=assignment,
    )

    return assignment
