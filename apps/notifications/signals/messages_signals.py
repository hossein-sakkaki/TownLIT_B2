# apps/notifications/signals/messages_signals.py

import logging
from django.db.models.signals import post_save 
from django.dispatch import receiver

from apps.conversation.models import Message
from apps.notifications.services.services import create_and_dispatch_notification

logger = logging.getLogger(__name__)


def _build_message_link(dialogue, message) -> str:
    """
    Build a deep link to the dialogue UI focusing on this message.
    Adjust the URL/query according to your frontend routing.
    """
    if not dialogue:
        return "/conversation/" 

    base_url = None

    # Try canonical URL of the dialogue first
    if hasattr(dialogue, "get_absolute_url"):
        try:
            base_url = dialogue.get_absolute_url()
        except Exception as e:
            logger.debug(
                "[Notif][Message] get_absolute_url failed for dialogue %s: %s",
                getattr(dialogue, "id", None),
                e,
            )

    # Fallback if get_absolute_url is missing or failed
    if not base_url:
        # ⚠️ If you prefer /conversation/{id}/ change slug → id
        base_url = f"/conversation/{dialogue.slug}/"

    return f"{base_url}?focus=message-{message.id}"


def _classify_message_kind(msg: Message) -> str:
    """
    Classify message kind based on Message model fields (NO decryption).
    Returns one of: 'text', 'voice', 'video', 'image', 'file'.
    """

    # Debug log to help if something goes wrong
    logger.debug(
        "[Notif][MessageKind] msg_id=%s | image=%s | video=%s | file=%s | audio=%s",
        getattr(msg, "id", None),
        bool(msg.image),
        bool(msg.video),
        bool(msg.file),
        bool(msg.audio),
    )

    # Voice / audio
    if msg.audio:
        return "voice"

    # Video
    if msg.video:
        return "video"

    # Image
    if msg.image:
        return "image"

    # Generic file
    if msg.file:
        return "file"

    # Fallback: assume text-only (encrypted or not)
    return "text"


def _build_notification_message(actor, msg_kind: str) -> str:
    """
    Build human-readable notification text based on message kind.
    We NEVER include decrypted content (E2EE remains intact).
    """
    username = getattr(actor, "username", "Someone")

    if msg_kind == "voice":
        return f"New voice message from {username}"
    if msg_kind == "video":
        return f"New video message from {username}"
    if msg_kind == "image":
        return f"New image from {username}"
    if msg_kind == "file":
        return f"New file from {username}"

    # Default: text message
    return f"New message from {username}"


@receiver(post_save, sender=Message, dispatch_uid="notif.message_new_v1")
def on_message_created(sender, instance: Message, created, **kwargs):
    """
    Create Notification (DB + Push + Email) when a new message is created.

    WebSocket streaming for messages is handled by the conversation app;
    here we only fan-out high-level notifications.
    """
    if not created:
        return

    # Sender user
    actor = getattr(instance, "sender", None)
    # Dialogue / conversation container
    dialogue = getattr(instance, "dialogue", None)

    if not actor or not dialogue:
        logger.debug(
            "[Notif][Message] Missing actor or dialogue for message %s",
            instance.id,
        )
        return

    # All participants except the sender
    recipients_qs = dialogue.participants.exclude(id=actor.id)

    if not recipients_qs.exists():
        logger.debug(
            "[Notif][Message] No recipients for message %s",
            instance.id,
        )
        return

    # Notification type based on direct vs group
    notif_type = (
        "new_message_group"
        if getattr(dialogue, "is_group", False)
        else "new_message_direct"
    )

    # Build deep-link once per message
    link = _build_message_link(dialogue, instance)

    # Classify message kind once
    msg_kind = _classify_message_kind(instance)

    for recipient in recipients_qs:
        # Safety: skip sender (should already be excluded above)
        if recipient.id == actor.id:
            continue

        # Human readable notification message (no content preview)
        msg_text = _build_notification_message(actor, msg_kind)

        create_and_dispatch_notification(
            recipient=recipient,
            actor=actor,
            notif_type=notif_type,
            message=msg_text,
            target_obj=dialogue,   # used for link resolution fallback
            action_obj=instance,   # the Message itself
            link=link,
            extra_payload={
                "dialogue_id": dialogue.id,
                "message_id": instance.id,
                "is_group": getattr(dialogue, "is_group", False),
                "message_kind": msg_kind,
            },
        )

        logger.debug(
            "[Notif][Message] %s (%s) → %s (dialogue=%s, message=%s, link=%s)",
            notif_type,
            msg_kind,
            recipient.username,
            dialogue.id,
            instance.id,
            link,
        )
