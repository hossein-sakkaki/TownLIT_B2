# apps/conversation/services/organization/direct_notifications.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-16.
#

from __future__ import annotations

from apps.conversation.models import Message
from apps.notifications.services.services import dispatch_push_only_notification

from .direct_realtime import organization_direct_operator_users


def _display_name(user) -> str:
    full_name = " ".join(
        part.strip()
        for part in (
            getattr(user, "name", "") or "",
            getattr(user, "family", "") or "",
        )
        if part and part.strip()
    )
    return full_name or getattr(user, "username", None) or "A user"


def _attribution(message):
    try:
        return message.organization_attribution
    except Exception:
        return None



def _message_kind(message) -> str:
    if getattr(message, "image", None):
        return "image"
    if getattr(message, "video", None):
        return "video"
    if getattr(message, "audio", None):
        return "audio"
    if getattr(message, "file", None):
        return "file"
    return "text"


def _message_noun(message) -> str:
    return {
        "image": "photo",
        "video": "video",
        "audio": "voice message",
        "file": "file",
    }.get(_message_kind(message), "message")

def _organization_push_text(message, organization_name: str) -> str:
    if _message_kind(message) == "text":
        return f"{organization_name} replied to your message."
    return f"{organization_name} sent you a {_message_noun(message)}."


def _participant_push_text(message, participant_name: str, organization_name: str) -> str:
    if _message_kind(message) == "text":
        return f"{participant_name} sent a message to {organization_name}."
    return (
        f"{participant_name} sent a {_message_noun(message)} "
        f"to {organization_name}."
    )


def notify_organization_direct_message_push(message_id: int) -> None:
    """Send Organization Direct push without creating Notification rows."""
    message = (
        Message.objects
        .select_related(
            "sender",
            "dialogue__organization_context__organization",
            "dialogue__organization_context__participant_user",
            "organization_attribution__organization",
        )
        .filter(pk=message_id)
        .first()
    )
    if not message or not message.is_delivery_ready:
        return

    context = message.dialogue.organization_context
    organization = context.organization
    attribution = _attribution(message)

    base_payload = {
        "dialogue_id": str(message.dialogue_id),
        "dialogue_slug": message.dialogue.slug or "",
        "message_id": str(message.id),
        "is_group": "false",
        "message_kind": _message_kind(message),
        "conversation_context": "organization_direct",
        "organization_public_id": str(organization.public_id),
        "organization_slug": organization.slug,
        "organization_name": organization.name,
    }

    if attribution is not None:
        recipient = context.participant_user
        link = f"/conversation/{message.dialogue.slug}?focus=message-{message.id}"
        dispatch_push_only_notification(
            recipient=recipient,
            actor=None,
            notif_type="new_message_direct",
            message=f"{organization.name} sent you a {_message_noun(message)}.",
            link=link,
            extra_payload={
                **base_payload,
                "conversation_destination": "personal_messenger",
                "conversation_link": link,
                "sender_type": "organization",
            },
        )
        return

    participant_name = _display_name(message.sender)
    link = (
        f"/organizations/{organization.slug}/messenger/conversations/"
        f"{message.dialogue.slug}?focus=message-{message.id}"
    )
    for recipient in organization_direct_operator_users(organization=organization):
        dispatch_push_only_notification(
            recipient=recipient,
            actor=None,
            notif_type="new_message_direct",
            message=f"{participant_name} sent a {_message_noun(message)} to {organization.name}.",
            link=link,
            extra_payload={
                **base_payload,
                "conversation_destination": "organization_workspace",
                "conversation_link": link,
                "sender_type": "user",
                "participant_user_id": str(message.sender_id),
            },
        )

