# apps/notifications/signals/messages_signals.py

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.conversation.models import Message
from apps.conversation.services.boundary_access import (
    should_send_conversation_notification,
)
from apps.notifications.services.services import dispatch_push_only_notification

logger = logging.getLogger(__name__)


def _dialogue_slug(dialogue) -> str | None:
    """Return dialogue slug safely."""
    slug = getattr(dialogue, "slug", None)
    return str(slug) if slug else None


def _build_message_link(dialogue, message: Message) -> str:
    """
    Build a stable messenger deep link.

    Web can route this as a normal path.
    iOS can detect /conversation/... and open Messenger.
    """
    if not dialogue:
        return "/conversation"

    slug = _dialogue_slug(dialogue)

    if slug:
        base_url = f"/conversation/{slug}"
    else:
        base_url = f"/conversation/{dialogue.id}"

    return f"{base_url}?focus=message-{message.id}"


def _classify_message_kind(msg: Message) -> str:
    """
    Classify message kind without decrypting content.
    E2EE content must never be included in notification text.
    """

    if getattr(msg, "audio", None):
        return "voice"

    if getattr(msg, "video", None):
        return "video"

    if getattr(msg, "image", None):
        return "image"

    if getattr(msg, "file", None):
        return "file"

    return "text"


def _actor_display_name(actor) -> str:
    """Return a safe sender display name."""
    if not actor:
        return "Someone"

    full_name = " ".join(
        part.strip()
        for part in [
            getattr(actor, "name", "") or "",
            getattr(actor, "family", "") or "",
        ]
        if part and part.strip()
    )

    if full_name:
        return full_name

    username = getattr(actor, "username", None)
    if username:
        return str(username)

    return "Someone"


def _build_notification_message(
    *,
    actor,
    msg_kind: str,
    is_group: bool,
    dialogue,
) -> str:
    """
    Build safe notification text.
    Never include decrypted/private message content.
    """
    sender = _actor_display_name(actor)

    if msg_kind == "voice":
        base = f"New voice message from {sender}"
    elif msg_kind == "video":
        base = f"New video message from {sender}"
    elif msg_kind == "image":
        base = f"New image from {sender}"
    elif msg_kind == "file":
        base = f"New file from {sender}"
    else:
        base = f"New message from {sender}"

    if not is_group:
        return base

    group_name = getattr(dialogue, "group_name", None)
    if group_name:
        return f"{base} in {group_name}"

    return base


def _should_skip_message_notification(instance: Message) -> bool:
    """Skip messages that should not create user-facing notifications."""
    if getattr(instance, "is_deleted", False):
        return True

    if getattr(instance, "deleted_for_everyone", False):
        return True

    # System messages should not send push notifications unless explicitly enabled later.
    if getattr(instance, "is_system", False):
        return True

    system_event_type = getattr(instance, "system_event_type", None)
    if system_event_type:
        return True

    return False


def _conversation_notification_allowed(
    *,
    recipient,
    actor,
) -> bool:
    """
    Apply conversation interruption policy.

    Current helper signature:
        should_send_conversation_notification(*, actor, recipient)
    """
    try:
        return bool(
            should_send_conversation_notification(
                actor=actor,
                recipient=recipient,
            )
        )
    except Exception:
        logger.warning(
            "[Notif][Message] Conversation notification policy check failed. "
            "Falling back to centralized delivery policy.",
            exc_info=True,
        )
        return True


@receiver(post_save, sender=Message, dispatch_uid="notif.message_new_v1")
def on_message_created(sender, instance: Message, created, **kwargs):
    """
    Create notification for a new conversation message.

    Message websocket delivery remains owned by the conversation app.
    This signal only creates high-level DB notification + WS/push fan-out.
    """
    if not created:
        return

    if _should_skip_message_notification(instance):
        return

    actor = getattr(instance, "sender", None)
    dialogue = getattr(instance, "dialogue", None)

    if not actor or not dialogue:
        return

    recipients_qs = dialogue.participants.exclude(id=actor.id)

    if not recipients_qs.exists():
        return

    is_group = bool(getattr(dialogue, "is_group", False))
    notif_type = "new_message_group" if is_group else "new_message_direct"

    dialogue_slug = _dialogue_slug(dialogue)
    link = _build_message_link(dialogue, instance)
    msg_kind = _classify_message_kind(instance)

    for recipient in recipients_qs:
        if recipient.id == actor.id:
            continue

        if not _conversation_notification_allowed(
            recipient=recipient,
            actor=actor,
        ):
            continue

        msg_text = _build_notification_message(
            actor=actor,
            msg_kind=msg_kind,
            is_group=is_group,
            dialogue=dialogue,
        )

        extra_payload = {
            "dialogue_id": str(dialogue.id),
            "dialogue_slug": dialogue_slug or "",
            "message_id": str(instance.id),
            "is_group": str(is_group).lower(),
            "message_kind": msg_kind,
            "conversation_link": link,
        }

        dispatch_push_only_notification(
            recipient=recipient,
            actor=actor,
            notif_type=notif_type,
            message=msg_text,
            link=link,
            extra_payload=extra_payload,
        )

        
       