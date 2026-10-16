# apps/conversation/services/organization/direct_workflow.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from __future__ import annotations

from django.db import transaction

from apps.conversation.constants import (
    OrganizationConversationContextType,
    OrganizationConversationStatus,
    OrganizationConversationWaitingFor,
)
from apps.conversation.models import OrganizationDialogueContext
from apps.organizations.constants import (
    ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES,
    OrganizationAuditAction,
    OrganizationAuditSource,
    OrganizationPermissionKey,
)
from apps.organizations.models import OrganizationMembership
from apps.organizations.services.access import user_has_organization_permission_strict

from .direct_access import (
    organization_operator_can_assign,
    organization_operator_can_manage,
)
from .direct_audit import log_organization_direct_audit


def _error(code: str, message: str, status_code: int):
    return {
        "ok": False,
        "code": code,
        "message": message,
        "status": status_code,
    }


def _success(payload: dict):
    return {
        "ok": True,
        "payload": payload,
    }



def _schedule_thread_update(context_id, *, reason):
    from .direct_realtime import schedule_organization_direct_thread_update

    schedule_organization_direct_thread_update(context_id, reason=reason)

def participant_message_state(current_status: str) -> tuple[str, str, bool]:
    """Return status, waiting_for, and whether this message reopens a thread."""
    reopened = current_status == OrganizationConversationStatus.RESOLVED
    return (
        OrganizationConversationStatus.OPEN,
        OrganizationConversationWaitingFor.ORGANIZATION,
        reopened,
    )


def organization_reply_state(current_status: str) -> tuple[str, str, bool]:
    reopened = current_status == OrganizationConversationStatus.RESOLVED
    return (
        OrganizationConversationStatus.OPEN,
        OrganizationConversationWaitingFor.PARTICIPANT,
        reopened,
    )


def _apply_context_state(*, context, status, waiting_for):
    changed_fields = []
    if context.status != status:
        context.status = status
        changed_fields.append("status")
    if context.waiting_for != waiting_for:
        context.waiting_for = waiting_for
        changed_fields.append("waiting_for")
    if changed_fields:
        context.save(update_fields=[*changed_fields, "updated_at"])
    return changed_fields


def mark_after_participant_message(*, context, actor):
    status, waiting_for, reopened = participant_message_state(context.status)
    _apply_context_state(
        context=context,
        status=status,
        waiting_for=waiting_for,
    )
    if reopened:
        log_organization_direct_audit(
            context=context,
            action=OrganizationAuditAction.MESSENGER_THREAD_REOPENED,
            actor=actor,
            metadata={"reason": "participant_message"},
        )
    return reopened


def mark_after_organization_reply(*, context, actor, actor_membership):
    status, waiting_for, reopened = organization_reply_state(context.status)
    _apply_context_state(
        context=context,
        status=status,
        waiting_for=waiting_for,
    )
    if reopened:
        log_organization_direct_audit(
            context=context,
            action=OrganizationAuditAction.MESSENGER_THREAD_REOPENED,
            actor=actor,
            membership=actor_membership,
            metadata={"reason": "organization_reply"},
        )
    return reopened


def membership_is_assignable_to_messenger(membership) -> bool:
    if not membership:
        return False
    if membership.status not in ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES:
        return False
    user = membership.member.user
    organization = membership.organization
    return any(
        user_has_organization_permission_strict(
            user=user,
            organization=organization,
            permission_key=key,
        )
        for key in (
            OrganizationPermissionKey.REPLY_MESSENGER,
            OrganizationPermissionKey.MANAGE_MESSENGER,
        )
    )


@transaction.atomic
def assign_organization_direct_thread(
    *,
    context,
    acting_user,
    target_membership=None,
):
    context = (
        OrganizationDialogueContext.objects
        .select_for_update()
        .select_related(
            "dialogue",
            "organization",
            "participant_user",
            "assigned_to_membership__member__user",
        )
        .get(pk=context.pk)
    )

    if context.context_type != OrganizationConversationContextType.DIRECT:
        return _error(
            "organization_direct_required",
            "Assignment is only available for Organization Direct conversations.",
            400,
        )

    if not organization_operator_can_assign(
        user=acting_user,
        organization=context.organization,
    ):
        return _error(
            "organization_assignment_forbidden",
            "Assign Organization Messenger permission is required.",
            403,
        )

    if context.status == OrganizationConversationStatus.CLOSED:
        return _error(
            "organization_conversation_closed",
            "Closed Organization conversations cannot be assigned.",
            409,
        )

    if target_membership is not None:
        if target_membership.organization_id != context.organization_id:
            return _error(
                "invalid_assignment_target",
                "Assignment target must belong to this Organization.",
                400,
            )
        if not membership_is_assignable_to_messenger(target_membership):
            return _error(
                "invalid_assignment_target",
                "Assignment target must be an active Messenger operator who can reply.",
                400,
            )

    previous_membership = context.assigned_to_membership
    previous_id = context.assigned_to_membership_id
    target_id = getattr(target_membership, "id", None)

    if previous_id == target_id:
        return _success({"context": context, "changed": False})

    context.assigned_to_membership = target_membership
    context.full_clean()
    context.save(update_fields=["assigned_to_membership", "updated_at"])

    if target_membership is None:
        action = OrganizationAuditAction.MESSENGER_THREAD_UNASSIGNED
        audit_membership = previous_membership
    else:
        action = OrganizationAuditAction.MESSENGER_THREAD_ASSIGNED
        audit_membership = target_membership

    log_organization_direct_audit(
        context=context,
        action=action,
        actor=acting_user,
        membership=audit_membership,
        metadata={
            "previous_membership_id": previous_id,
            "assigned_membership_id": target_id,
        },
    )
    _schedule_thread_update(context.id, reason="assignment_changed")

    return _success({"context": context, "changed": True})


@transaction.atomic
def transition_organization_direct_thread(
    *,
    context,
    acting_user,
    target_status,
):
    context = (
        OrganizationDialogueContext.objects
        .select_for_update()
        .select_related(
            "dialogue",
            "organization",
            "participant_user",
            "assigned_to_membership",
        )
        .get(pk=context.pk)
    )

    if context.context_type != OrganizationConversationContextType.DIRECT:
        return _error(
            "organization_direct_required",
            "Lifecycle actions require an Organization Direct conversation.",
            400,
        )

    if not organization_operator_can_manage(
        user=acting_user,
        organization=context.organization,
    ):
        return _error(
            "organization_manage_forbidden",
            "Manage Organization Messenger permission is required.",
            403,
        )

    action_map = {
        OrganizationConversationStatus.RESOLVED: (
            OrganizationAuditAction.MESSENGER_THREAD_RESOLVED
        ),
        OrganizationConversationStatus.OPEN: (
            OrganizationAuditAction.MESSENGER_THREAD_REOPENED
        ),
        OrganizationConversationStatus.CLOSED: (
            OrganizationAuditAction.MESSENGER_THREAD_CLOSED
        ),
    }
    if target_status not in action_map:
        return _error(
            "invalid_conversation_status",
            "Unsupported Organization conversation status.",
            400,
        )

    if context.status == target_status:
        return _success({"context": context, "changed": False})

    previous_status = context.status
    context.status = target_status
    context.waiting_for = OrganizationConversationWaitingFor.NONE
    context.full_clean()
    context.save(update_fields=["status", "waiting_for", "updated_at"])

    log_organization_direct_audit(
        context=context,
        action=action_map[target_status],
        actor=acting_user,
        metadata={
            "previous_status": previous_status,
            "new_status": target_status,
            "reason": "operator_action",
        },
    )
    _schedule_thread_update(context.id, reason="lifecycle_changed")

    return _success({"context": context, "changed": True})


@transaction.atomic
def clear_invalid_direct_assignments_for_membership_id(membership_id):
    membership = (
        OrganizationMembership.objects
        .select_related("organization", "member__user")
        .filter(pk=membership_id)
        .first()
    )
    if membership and membership_is_assignable_to_messenger(membership):
        return 0

    contexts = list(
        OrganizationDialogueContext.objects
        .select_for_update()
        .select_related("dialogue", "organization", "participant_user")
        .filter(
            context_type=OrganizationConversationContextType.DIRECT,
            assigned_to_membership_id=membership_id,
        )
    )

    for context in contexts:
        context.assigned_to_membership = None
        context.save(update_fields=["assigned_to_membership", "updated_at"])
        log_organization_direct_audit(
            context=context,
            action=OrganizationAuditAction.MESSENGER_THREAD_UNASSIGNED,
            actor=None,
            metadata={
                "previous_membership_id": membership_id,
                "reason": "assignment_target_no_longer_eligible",
            },
            source=OrganizationAuditSource.SYSTEM,
        )
        _schedule_thread_update(context.id, reason="assignment_invalidated")

    return len(contexts)
