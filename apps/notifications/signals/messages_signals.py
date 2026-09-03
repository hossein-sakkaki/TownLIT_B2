# apps/notifications/signals/messages_signals.py

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.conversation.models import Message
from apps.conversation.services.boundary_access import (
    should_send_conversation_notification,
)
from apps.notifications.services.presentation import build_messenger_message
from apps.notifications.services.services import dispatch_push_only_notification

logger = logging.getLogger(__name__)


def _dialogue_slug(dialogue) -> str | None:
    """Return dialogue slug safely."""
    slug = getattr(dialogue, "slug", None)
    return str(slug) if slug else None


def _build_message_link(dialogue, message: Message) -> str:
    """Build a stable Messenger deep link."""
    if not dialogue:
        return "/conversation"

    slug = _dialogue_slug(dialogue)
    base_url = (
        f"/conversation/{slug}"
        if slug
        else f"/conversation/{dialogue.id}"
    )

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


def _should_skip_message_notification(instance: Message) -> bool:
    """Skip messages that should not create user-facing notifications."""
    if getattr(instance, "is_deleted", False):
        return True

    if getattr(instance, "deleted_for_everyone", False):
        return True

    if getattr(instance, "is_system", False):
        return True

    if getattr(instance, "system_event_type", None):
        return True

    return False


def _conversation_notification_allowed(*, recipient, actor) -> bool:
    """Apply Messenger interruption policy."""
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
    Send a privacy-safe push for a new conversation message.

    Message content is never decrypted or included in push copy.
    """
    if not created or _should_skip_message_notification(instance):
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
    message_kind = _classify_message_kind(instance)
    group_name = getattr(dialogue, "group_name", None)

    for recipient in recipients_qs:
        if recipient.id == actor.id:
            continue

        if not _conversation_notification_allowed(
            recipient=recipient,
            actor=actor,
        ):
            continue

        message = build_messenger_message(
            actor,
            is_group=is_group,
            group_name=group_name,
        )

        extra_payload = {
            "dialogue_id": str(dialogue.id),
            "dialogue_slug": dialogue_slug or "",
            "message_id": str(instance.id),
            "is_group": str(is_group).lower(),
            "message_kind": message_kind,
            "conversation_link": link,
        }

        dispatch_push_only_notification(
            recipient=recipient,
            actor=actor,
            notif_type=notif_type,
            message=message,
            link=link,
            extra_payload=extra_payload,
        )