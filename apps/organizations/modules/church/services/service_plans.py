# apps/organizations/modules/church/services/service_plans.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-31.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.organizations.modules.church.constants import (
    ChurchAuditEvent,
    ChurchGatheringOccurrenceStatus,
    ChurchPermissionKey,
    ChurchServicePlanStatus,
    ChurchServingAssignmentStatus,
)
from apps.organizations.modules.church.models import (
    ChurchServicePlan,
    ChurchServicePlanItem,
    ChurchServingAssignment,
)
from apps.organizations.modules.church.services.access import ensure_church_permission
from apps.organizations.modules.church.services.audit import record_church_audit


@transaction.atomic
def create_church_service_plan(
    *,
    occurrence,
    actor,
    theme=None,
    internal_notes=None,
):
    occurrence = (
        occurrence.__class__.objects
        .select_for_update()
        .select_related("workspace__activation__organization")
        .get(pk=occurrence.pk)
    )

    ensure_church_permission(
        actor=actor,
        workspace=occurrence.workspace,
        permission_key=ChurchPermissionKey.MANAGE_SERVICE_PLANS,
    )

    if occurrence.status == ChurchGatheringOccurrenceStatus.CANCELED:
        raise ValidationError(
            "A service plan cannot be created for a canceled gathering."
        )

    existing = ChurchServicePlan.objects.filter(
        occurrence=occurrence,
    ).first()
    if existing:
        return existing

    plan = ChurchServicePlan(
        workspace=occurrence.workspace,
        occurrence=occurrence,
        theme=theme,
        internal_notes=internal_notes,
        created_by=actor,
    )
    plan.full_clean()
    plan.save()

    record_church_audit(
        workspace=plan.workspace,
        event=ChurchAuditEvent.SERVICE_PLAN_CREATED,
        actor=actor,
        entity=plan,
        metadata={
            "occurrence_public_id": str(occurrence.public_id),
        },
    )

    return plan


@transaction.atomic
def update_church_service_plan(*, plan, actor, theme=None, internal_notes=None):
    plan = (
        ChurchServicePlan.objects
        .select_for_update()
        .select_related("workspace__activation__organization", "occurrence")
        .get(pk=plan.pk)
    )

    ensure_church_permission(
        actor=actor,
        workspace=plan.workspace,
        permission_key=ChurchPermissionKey.MANAGE_SERVICE_PLANS,
    )

    if plan.status in {
        ChurchServicePlanStatus.COMPLETED,
        ChurchServicePlanStatus.CANCELED,
    }:
        raise ValidationError("Completed or canceled service plans cannot be edited.")

    if theme is not None:
        plan.theme = theme
    if internal_notes is not None:
        plan.internal_notes = internal_notes

    plan.full_clean()
    plan.save()

    record_church_audit(
        workspace=plan.workspace,
        event=ChurchAuditEvent.SERVICE_PLAN_UPDATED,
        actor=actor,
        entity=plan,
    )

    return plan


@transaction.atomic
def add_church_service_plan_item(
    *,
    plan,
    actor,
    item_type,
    title,
    serving_team=None,
    ministry=None,
    notes=None,
    planned_duration_seconds=0,
    sort_order=100,
    is_optional=False,
    is_internal_only=False,
):
    plan = (
        ChurchServicePlan.objects
        .select_for_update()
        .select_related("workspace__activation__organization")
        .get(pk=plan.pk)
    )

    ensure_church_permission(
        actor=actor,
        workspace=plan.workspace,
        permission_key=ChurchPermissionKey.MANAGE_SERVICE_PLANS,
    )

    if plan.status in {
        ChurchServicePlanStatus.COMPLETED,
        ChurchServicePlanStatus.CANCELED,
    }:
        raise ValidationError("Items cannot be added to a closed service plan.")

    item = ChurchServicePlanItem(
        service_plan=plan,
        serving_team=serving_team,
        ministry=ministry,
        item_type=item_type,
        title=title,
        notes=notes,
        planned_duration_seconds=planned_duration_seconds,
        sort_order=sort_order,
        is_optional=is_optional,
        is_internal_only=is_internal_only,
    )
    item.full_clean()
    item.save()

    record_church_audit(
        workspace=plan.workspace,
        event=ChurchAuditEvent.SERVICE_PLAN_ITEM_ADDED,
        actor=actor,
        entity=item,
        metadata={
            "service_plan_public_id": str(plan.public_id),
            "item_type": item.item_type,
        },
    )

    return item


@transaction.atomic
def update_church_service_plan_item(*, item, actor, **changes):
    item = (
        ChurchServicePlanItem.objects
        .select_for_update()
        .select_related("service_plan__workspace__activation__organization")
        .get(pk=item.pk)
    )
    plan = item.service_plan

    ensure_church_permission(
        actor=actor,
        workspace=plan.workspace,
        permission_key=ChurchPermissionKey.MANAGE_SERVICE_PLANS,
    )

    if plan.status in {
        ChurchServicePlanStatus.COMPLETED,
        ChurchServicePlanStatus.CANCELED,
    }:
        raise ValidationError("Items on a closed service plan cannot be edited.")

    allowed = {
        "serving_team",
        "ministry",
        "item_type",
        "title",
        "notes",
        "planned_duration_seconds",
        "sort_order",
        "is_optional",
        "is_internal_only",
    }

    for field, value in changes.items():
        if field not in allowed:
            raise ValidationError(f"Unsupported service plan item field: {field}.")
        setattr(item, field, value)

    item.full_clean()
    item.save()

    record_church_audit(
        workspace=plan.workspace,
        event=ChurchAuditEvent.SERVICE_PLAN_ITEM_UPDATED,
        actor=actor,
        entity=item,
    )

    return item


@transaction.atomic
def remove_church_service_plan_item(*, item, actor):
    item = (
        ChurchServicePlanItem.objects
        .select_for_update()
        .select_related("service_plan__workspace__activation__organization")
        .get(pk=item.pk)
    )
    plan = item.service_plan

    ensure_church_permission(
        actor=actor,
        workspace=plan.workspace,
        permission_key=ChurchPermissionKey.MANAGE_SERVICE_PLANS,
    )

    if plan.status in {
        ChurchServicePlanStatus.COMPLETED,
        ChurchServicePlanStatus.CANCELED,
    }:
        raise ValidationError("Items on a closed service plan cannot be removed.")

    public_id = item.public_id
    item_type = item.item_type
    item.delete()

    record_church_audit(
        workspace=plan.workspace,
        event=ChurchAuditEvent.SERVICE_PLAN_ITEM_REMOVED,
        actor=actor,
        entity_type="ChurchServicePlanItem",
        entity_public_id=public_id,
        metadata={
            "item_type": item_type,
            "service_plan_public_id": str(plan.public_id),
        },
    )


@transaction.atomic
def publish_church_service_plan(*, plan, actor, now=None):
    now = now or timezone.now()
    plan = (
        ChurchServicePlan.objects
        .select_for_update()
        .select_related("workspace__activation__organization")
        .get(pk=plan.pk)
    )

    ensure_church_permission(
        actor=actor,
        workspace=plan.workspace,
        permission_key=ChurchPermissionKey.MANAGE_SERVICE_PLANS,
    )

    if plan.status == ChurchServicePlanStatus.PUBLISHED:
        return plan
    if plan.status != ChurchServicePlanStatus.DRAFT:
        raise ValidationError("Only draft service plans can be published.")
    if not plan.items.exists():
        raise ValidationError("A service plan requires at least one item before publishing.")

    plan.status = ChurchServicePlanStatus.PUBLISHED
    plan.published_at = now
    plan.published_by = actor
    plan.full_clean()
    plan.save(
        update_fields=["status", "published_at", "published_by", "updated_at"]
    )

    record_church_audit(
        workspace=plan.workspace,
        event=ChurchAuditEvent.SERVICE_PLAN_PUBLISHED,
        actor=actor,
        entity=plan,
    )

    return plan


@transaction.atomic
def complete_church_service_plan(*, plan, actor, now=None):
    now = now or timezone.now()
    plan = (
        ChurchServicePlan.objects
        .select_for_update()
        .select_related("workspace__activation__organization")
        .get(pk=plan.pk)
    )

    ensure_church_permission(
        actor=actor,
        workspace=plan.workspace,
        permission_key=ChurchPermissionKey.MANAGE_SERVICE_PLANS,
    )

    if plan.status == ChurchServicePlanStatus.COMPLETED:
        return plan
    if plan.status != ChurchServicePlanStatus.PUBLISHED:
        raise ValidationError("Only published service plans can be completed.")

    if plan.serving_assignments.filter(
        status__in={
            ChurchServingAssignmentStatus.INVITED,
            ChurchServingAssignmentStatus.CONFIRMED,
        }
    ).exists():
        raise ValidationError(
            "Resolve all invited or confirmed serving assignments before completing the service plan."
        )

    plan.status = ChurchServicePlanStatus.COMPLETED
    plan.completed_at = now
    plan.completed_by = actor
    plan.full_clean()
    plan.save(
        update_fields=["status", "completed_at", "completed_by", "updated_at"]
    )

    record_church_audit(
        workspace=plan.workspace,
        event=ChurchAuditEvent.SERVICE_PLAN_COMPLETED,
        actor=actor,
        entity=plan,
    )

    return plan


@transaction.atomic
def cancel_church_service_plan(*, plan, actor, now=None):
    now = now or timezone.now()
    plan = (
        ChurchServicePlan.objects
        .select_for_update()
        .select_related("workspace__activation__organization")
        .get(pk=plan.pk)
    )

    ensure_church_permission(
        actor=actor,
        workspace=plan.workspace,
        permission_key=ChurchPermissionKey.MANAGE_SERVICE_PLANS,
    )

    if plan.status == ChurchServicePlanStatus.CANCELED:
        return plan
    if plan.status == ChurchServicePlanStatus.COMPLETED:
        raise ValidationError("Completed service plans cannot be canceled.")

    assignments_to_cancel = list(
        ChurchServingAssignment.objects
        .select_for_update()
        .filter(
            service_plan=plan,
            status__in={
                ChurchServingAssignmentStatus.INVITED,
                ChurchServingAssignmentStatus.CONFIRMED,
            },
        )
        .select_related("membership")
    )

    if any(assignment.checked_in_at for assignment in assignments_to_cancel):
        raise ValidationError(
            "Checked-in serving assignments must be completed before canceling the service plan."
        )

    for assignment in assignments_to_cancel:
        assignment.status = ChurchServingAssignmentStatus.CANCELED
        assignment.canceled_at = now
        assignment.canceled_by = actor
        assignment.full_clean()
        assignment.save(
            update_fields=[
                "status",
                "canceled_at",
                "canceled_by",
                "updated_at",
            ]
        )
        record_church_audit(
            workspace=plan.workspace,
            event=ChurchAuditEvent.SERVING_ASSIGNMENT_CANCELED,
            actor=actor,
            membership=assignment.membership,
            entity=assignment,
            metadata={"reason": "service_plan_canceled"},
        )

    plan.status = ChurchServicePlanStatus.CANCELED
    plan.canceled_at = now
    plan.canceled_by = actor
    plan.completed_at = None
    plan.completed_by = None
    plan.full_clean()
    plan.save(
        update_fields=[
            "status",
            "canceled_at",
            "canceled_by",
            "completed_at",
            "completed_by",
            "updated_at",
        ]
    )

    record_church_audit(
        workspace=plan.workspace,
        event=ChurchAuditEvent.SERVICE_PLAN_CANCELED,
        actor=actor,
        entity=plan,
    )

    return plan
