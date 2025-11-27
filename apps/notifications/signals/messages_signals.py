# apps/notifications/signals/messages_signals.py

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.conversation.models import Message
from apps.notifications.services import create_and_dispatch_notification

logger = logging.getLogger(__name__)


def _build_message_link(dialogue, message) -> str:
    """
    Build a deep link to the dialogue UI focusing on this message.
    Adjust the URL/query according to your frontend routing.
    """
    if not dialogue:
        return "/conversation/"

    # Try canonical URL of the dialogue first
    base_url = None
    if hasattr(dialogue, "get_absolute_url"):
        try:
            base_url = dialogue.get_absolute_url()
        except Exception as e:
            logger.debug(
                "[Notif][Message] get_absolute_url failed for dialogue %s: %s",
                getattr(dialogue, "id", None),
                e,
            )

    # Fallback if no get_absolute_url or it failed
    if not base_url:
        base_url = f"/conversation/{dialogue.slug}/"
    return f"{base_url}?focus=message-{message.id}"


@receiver(post_save, sender=Message, dispatch_uid="notif.message_new_v1")
def on_message_created(sender, instance: Message, created, **kwargs):
    """
    Create Notification (DB + WS + Push + Email) when a new message is created.
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

    for recipient in recipients_qs:
        if recipient.id == actor.id:
            continue

        msg_text = f"New message from {actor.username}"

        create_and_dispatch_notification(
            recipient=recipient,
            actor=actor,
            notif_type=notif_type,
            message=msg_text,
            target_obj=dialogue,
            action_obj=instance,
            link=link,
            extra_payload={
                "dialogue_id": dialogue.id,
                "message_id": instance.id,
                "is_group": getattr(dialogue, "is_group", False),
            },
        )

        logger.debug(
            "[Notif][Message] %s → %s (dialogue=%s, message=%s, link=%s)",
            notif_type,
            recipient.username,
            dialogue.id,
            instance.id,
            link,
        )
