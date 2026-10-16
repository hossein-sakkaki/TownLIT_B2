# apps/conversation/services/organization/direct_media.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-16.
# Last Update by Hossein Sakkaki on 2026-10-16.
#

from __future__ import annotations

from django.db import transaction

from apps.conversation.constants import OrganizationConversationContextType
from apps.conversation.models import OrganizationDialogueContext
from apps.conversation.policies import ConversationAccessPolicy
from apps.conversation.services.message_creation import create_file_message
from apps.organizations.services.access import get_current_membership_for_user

from .attribution import create_organization_message_attribution
from .direct_access import organization_operator_can_reply
from .direct_realtime import schedule_organization_direct_message_realtime
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


def _locked_direct_context(context):
    return (
        OrganizationDialogueContext.objects
        .select_for_update()
        .select_related(
            "dialogue",
            "organization",
            "participant_user",
        )
        .get(pk=context.pk)
    )


def _authorize_sender(*, context, acting_user):
    is_participant = acting_user.id == context.participant_user_id

    if is_participant:
        access = ConversationAccessPolicy.can_send_as_self(
            dialogue=context.dialogue,
            user=acting_user,
        )
        if not access.allowed:
            return _error(
                access.code or "FORBIDDEN",
                access.message or "Conversation access denied.",
                403,
            )

        return {
            "ok": True,
            "is_participant": True,
            "actor_membership": None,
        }

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

    return {
        "ok": True,
        "is_participant": False,
        "actor_membership": actor_membership,
    }


@transaction.atomic
def create_organization_direct_media_message(
    *,
    context,
    acting_user,
    uploaded_file,
    field_name,
    is_encrypted_file,
    encrypted_for_device=None,
    aes_key_encrypted_bytes=None,
    encrypted_keys_per_device=None,
    reply_to_message_id=None,
):
    """Create Organization Direct media through the shared media engine."""
    context = _locked_direct_context(context)

    if context.context_type != OrganizationConversationContextType.DIRECT:
        return _error(
            "organization_direct_required",
            "Organization Direct conversation is required.",
            409,
        )

    authorization = _authorize_sender(
        context=context,
        acting_user=acting_user,
    )
    if not authorization.get("ok"):
        return authorization

    result = create_file_message(
        dialogue=context.dialogue,
        sender=acting_user,
        uploaded_file=uploaded_file,
        field_name=field_name,
        is_encrypted_file=is_encrypted_file,
        encrypted_for_device=encrypted_for_device,
        aes_key_encrypted_bytes=aes_key_encrypted_bytes,
        encrypted_keys_per_device=encrypted_keys_per_device,
        recipient_hidden_on_incoming=False,
        recipient=None,
        reply_to_message_id=reply_to_message_id,
        forwarded_from_message=None,
    )
    if not result.get("ok"):
        return result

    message = result["payload"]["message"]

    if not authorization["is_participant"]:
        create_organization_message_attribution(
            message=message,
            organization=context.organization,
            actor_membership=authorization["actor_membership"],
        )

    if message.is_delivery_ready:
        finalize_organization_direct_media_delivery(
            message=message,
            locked_context=context,
        )

    result["payload"]["context"] = context
    return result


@transaction.atomic
def finalize_organization_direct_media_delivery(
    *,
    message,
    locked_context=None,
):
    """Apply Organization workflow and realtime after media becomes deliverable."""
    message = (
        type(message).objects
        .select_for_update()
        .select_related(
            "sender",
            "dialogue__organization_context__organization",
            "dialogue__organization_context__participant_user",
            "organization_attribution__actor_membership",
        )
        .get(pk=message.pk)
    )

    if not message.is_delivery_ready:
        return False

    context = locked_context or _locked_direct_context(
        message.dialogue.organization_context
    )

    if context.context_type != OrganizationConversationContextType.DIRECT:
        return False

    try:
        attribution = message.organization_attribution
    except Exception:
        attribution = None

    if attribution is None:
        if message.sender_id != context.participant_user_id:
            return False

        mark_after_participant_message(
            context=context,
            actor=message.sender,
        )
        context.dialogue.deleted_by_users.remove(context.participant_user)
    else:
        mark_after_organization_reply(
            context=context,
            actor=message.sender,
            actor_membership=attribution.actor_membership,
        )
        context.dialogue.deleted_by_users.remove(context.participant_user)

    schedule_organization_direct_message_realtime(message.id)
    return True
