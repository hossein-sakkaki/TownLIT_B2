# apps/conversation/services/organization/direct_messages.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-18.
#

from __future__ import annotations

from django.db import transaction

from apps.conversation.constants import OrganizationConversationStatus
from apps.conversation.models import OrganizationDialogueContext
from apps.conversation.policies import ConversationAccessPolicy
from apps.conversation.services.message_creation import (
    create_backend_managed_text_message,
)
from apps.organizations.services.access import get_current_membership_for_user

from .attribution import create_organization_message_attribution
from .direct_access import organization_operator_can_reply, organization_operator_can_view
from .direct_dialogue import ensure_organization_direct_context
from .direct_selectors import organization_direct_unread_queryset
from .direct_realtime import (
    schedule_organization_direct_message_realtime,
    schedule_organization_direct_read_realtime,
)
from .direct_workflow import (
    mark_after_organization_reply,
    mark_after_participant_message,
)


def _error(code: str, message: str, status_code: int):
    return {
        "ok": False,
        "code": code,
        "message": message,
        "status": status_code,
    }


def _success(payload: dict, status_code: int = 200):
    return {
        "ok": True,
        "payload": payload,
        "status": status_code,
    }


@transaction.atomic
def send_organization_direct_participant_message(
    *,
    organization,
    participant_user,
    content,
    reply_to_message_id=None,
    client_request_id=None,
):
    plain_text = str(content or "").strip()
    if not plain_text:
        return _error(
            "BAD_REQUEST",
            "Message content is required.",
            400,
        )

    context_result = ensure_organization_direct_context(
        organization=organization,
        participant_user=participant_user,
    )
    if not context_result.ok:
        return _error(
            context_result.code,
            context_result.message,
            context_result.status,
        )

    context = context_result.context
    context = (
        OrganizationDialogueContext.objects
        .select_for_update()
        .select_related(
            "dialogue",
            "organization",
            "participant_user",
        )
        .get(pk=context.pk)
    )

    access = ConversationAccessPolicy.can_send_as_self(
        dialogue=context.dialogue,
        user=participant_user,
    )
    if not access.allowed:
        if context_result.created:
            transaction.set_rollback(True)
        return _error(
            access.code or "FORBIDDEN",
            access.message or "Conversation access denied.",
            403,
        )

    result = create_backend_managed_text_message(
        dialogue=context.dialogue,
        sender=participant_user,
        content=plain_text,
        reply_to_message_id=reply_to_message_id,
        client_request_id=client_request_id,
    )
    if not result.get("ok"):
        if context_result.created:
            transaction.set_rollback(True)
        return result

    message_created = bool(result["payload"].get("created", True))
    if message_created:
        mark_after_participant_message(
            context=context,
            actor=participant_user,
        )

        context.dialogue.deleted_by_users.remove(participant_user)
        schedule_organization_direct_message_realtime(
            result["payload"]["message"].id
        )

    return _success(
        {
            "context": context,
            "message": result["payload"]["message"],
            "created": context_result.created,
            "message_created": message_created,
            "idempotent_replay": bool(
                result["payload"].get("idempotent_replay", False)
            ),
        },
        201 if message_created else 200,
    )


@transaction.atomic
def send_organization_direct_reply(
    *,
    context,
    acting_user,
    content,
    reply_to_message_id=None,
    client_request_id=None,
):
    plain_text = str(content or "").strip()
    if not plain_text:
        return _error(
            "BAD_REQUEST",
            "Message content is required.",
            400,
        )

    context = (
        OrganizationDialogueContext.objects
        .select_for_update()
        .select_related(
            "dialogue",
            "organization",
            "participant_user",
        )
        .get(pk=context.pk)
    )

    if not organization_operator_can_reply(
        user=acting_user,
        organization=context.organization,
    ):
        return _error(
            "organization_reply_forbidden",
            "Reply as Organization permission is required.",
            403,
        )

    access = ConversationAccessPolicy.can_send_as_organization(
        dialogue=context.dialogue,
        user=acting_user,
    )
    if not access.allowed:
        return _error(
            access.code or "FORBIDDEN",
            access.message or "Conversation access denied.",
            403,
        )

    actor_membership = get_current_membership_for_user(
        organization=context.organization,
        user=acting_user,
    )
    if actor_membership is None:
        return _error(
            "organization_membership_required",
            "An active Organization membership is required.",
            403,
        )

    result = create_backend_managed_text_message(
        dialogue=context.dialogue,
        sender=acting_user,
        content=plain_text,
        reply_to_message_id=reply_to_message_id,
        client_request_id=client_request_id,
    )
    if not result.get("ok"):
        return result

    message = result["payload"]["message"]
    message_created = bool(result["payload"].get("created", True))

    if message_created:
        attribution = create_organization_message_attribution(
            message=message,
            organization=context.organization,
            actor_membership=actor_membership,
        )

        mark_after_organization_reply(
            context=context,
            actor=acting_user,
            actor_membership=actor_membership,
        )

        # A new Organization reply should make a previously hidden thread visible
        # again without restoring the participant's old soft-deleted messages.
        context.dialogue.deleted_by_users.remove(context.participant_user)
        schedule_organization_direct_message_realtime(message.id)
    else:
        try:
            attribution = message.organization_attribution
        except Exception:
            attribution = None

    return _success(
        {
            "context": context,
            "message": message,
            "attribution": attribution,
            "message_created": message_created,
            "idempotent_replay": bool(
                result["payload"].get("idempotent_replay", False)
            ),
        },
        201 if message_created else 200,
    )


@transaction.atomic
def mark_organization_direct_read_for_operator(*, context, acting_user):
    context = (
        OrganizationDialogueContext.objects
        .select_for_update()
        .select_related(
            "dialogue",
            "organization",
            "participant_user",
        )
        .get(pk=context.pk)
    )

    if not organization_operator_can_view(
        user=acting_user,
        organization=context.organization,
    ):
        return _error(
            "organization_messenger_forbidden",
            "Organization Messenger access is not permitted.",
            403,
        )

    access = ConversationAccessPolicy.can_view(
        dialogue=context.dialogue,
        user=acting_user,
    )
    if not access.allowed:
        return _error(
            access.code or "FORBIDDEN",
            access.message or "Conversation access denied.",
            403,
        )

    unread_messages = list(
        organization_direct_unread_queryset(
            context=context,
            operator_user=acting_user,
        ).only("id")
    )

    for message in unread_messages:
        message.seen_by_users.add(acting_user)

    schedule_organization_direct_read_realtime(
        context.id,
        reader_id=acting_user.id,
        read_message_ids=[message.id for message in unread_messages],
    )

    return _success(
        {
            "read_messages": [message.id for message in unread_messages],
        }
    )
