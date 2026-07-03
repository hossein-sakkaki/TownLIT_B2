# apps/conversation/services/messenger_notification_adapter.py

import logging
from typing import Iterable, Optional

from django.db import transaction

from apps.conversation.models import Message
from apps.conversation.services.boundary_access import (
    should_send_conversation_notification,
)
from apps.notifications.services.services import dispatch_push_only_notification

logger = logging.getLogger(__name__)


def _actor_display_name(actor) -> str:
    """Return a safe actor display name."""
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


def _dialogue_title(dialogue) -> str:
    """Return a safe dialogue title."""
    if not dialogue:
        return "conversation"

    if getattr(dialogue, "is_group", False):
        group_name = getattr(dialogue, "group_name", None)
        if group_name:
            return str(group_name)

        return "group conversation"

    return "conversation"


def _dialogue_slug(dialogue) -> Optional[str]:
    """Return dialogue slug safely."""
    slug = getattr(dialogue, "slug", None)
    return str(slug) if slug else None


def _message_link(dialogue, message_id: Optional[int] = None) -> str:
    """
    Build a stable messenger deep link.

    iOS can detect /conversation/... and open Messenger directly.
    """
    if not dialogue:
        return "/conversation"

    slug = _dialogue_slug(dialogue)

    if slug:
        base_url = f"/conversation/{slug}"
    else:
        base_url = f"/conversation/{dialogue.id}"

    if message_id:
        return f"{base_url}?focus=message-{message_id}"

    return base_url


def _conversation_notification_allowed(
    *,
    recipient,
    actor,
) -> bool:
    """Apply conversation interruption policy."""
    try:
        return bool(
            should_send_conversation_notification(
                actor=actor,
                recipient=recipient,
            )
        )
    except Exception:
        logger.warning(
            "[MessengerNotif] Policy check failed; allowing centralized fallback.",
            exc_info=True,
        )
        return True


def _recipient_can_receive_for_dialogue(
    *,
    dialogue,
    recipient,
) -> bool:
    """Check recipient still belongs to and can see the dialogue."""
    if not dialogue or not recipient:
        return False

    try:
        if not dialogue.participants.filter(id=recipient.id).exists():
            return False

        if dialogue.deleted_by_users.filter(id=recipient.id).exists():
            return False

        return True

    except Exception:
        logger.warning(
            "[MessengerNotif] Dialogue visibility check failed dialogue=%s recipient=%s",
            getattr(dialogue, "id", None),
            getattr(recipient, "id", None),
            exc_info=True,
        )
        return False


def _recipient_can_receive_for_message(
    *,
    message: Message,
    recipient,
) -> bool:
    """Check recipient can still see the message."""
    if not message or not recipient:
        return False

    dialogue = getattr(message, "dialogue", None)

    if not _recipient_can_receive_for_dialogue(
        dialogue=dialogue,
        recipient=recipient,
    ):
        return False

    try:
        if message.deleted_by_users.filter(id=recipient.id).exists():
            return False

        if getattr(message, "is_deleted", False):
            return False

        if getattr(message, "deleted_for_everyone", False):
            return False

        return True

    except Exception:
        logger.warning(
            "[MessengerNotif] Message visibility check failed message=%s recipient=%s",
            getattr(message, "id", None),
            getattr(recipient, "id", None),
            exc_info=True,
        )
        return False


def _dispatch_after_commit(
    *,
    recipient,
    actor,
    notif_type: str,
    message: str,
    link: str,
    extra_payload: dict,
) -> None:
    """Dispatch push-only after DB commit."""
    def _send():
        dispatch_push_only_notification(
            recipient=recipient,
            actor=actor,
            notif_type=notif_type,
            message=message,
            link=link,
            extra_payload=extra_payload,
        )

    if transaction.get_connection().in_atomic_block:
        transaction.on_commit(_send)
    else:
        _send()


def notify_group_created_or_user_added(
    *,
    dialogue,
    actor,
    recipients: Iterable,
) -> None:
    """
    Push-only notification for users added to a group.

    This does not create Notification rows and does not send notification WS.
    """
    if not dialogue or not getattr(dialogue, "is_group", False):
        return

    group_name = _dialogue_title(dialogue)
    actor_name = _actor_display_name(actor)
    link = _message_link(dialogue)

    dialogue_slug = _dialogue_slug(dialogue) or ""

    for recipient in recipients:
        if not recipient:
            continue

        if actor and getattr(recipient, "id", None) == getattr(actor, "id", None):
            continue

        if not _recipient_can_receive_for_dialogue(
            dialogue=dialogue,
            recipient=recipient,
        ):
            continue

        if not _conversation_notification_allowed(
            recipient=recipient,
            actor=actor,
        ):
            continue

        text = f"{actor_name} added you to {group_name}."

        extra_payload = {
            "dialogue_id": str(dialogue.id),
            "dialogue_slug": dialogue_slug,
            "message_id": "",
            "is_group": "true",
            "message_kind": "group_created",
            "conversation_link": link,
        }

        _dispatch_after_commit(
            recipient=recipient,
            actor=actor,
            notif_type="messenger_group_created",
            message=text,
            link=link,
            extra_payload=extra_payload,
        )


def notify_message_pinned(
    *,
    pin,
    actor,
) -> None:
    """
    Push-only notification when a group message is pinned.

    Private chat pin push is intentionally skipped for now.
    """
    if not pin:
        return

    dialogue = getattr(pin, "dialogue", None)
    message = getattr(pin, "message", None)

    if not dialogue or not message:
        return

    if not getattr(dialogue, "is_group", False):
        return

    group_name = _dialogue_title(dialogue)
    actor_name = _actor_display_name(actor)
    link = _message_link(dialogue, getattr(message, "id", None))

    dialogue_slug = _dialogue_slug(dialogue) or ""

    recipients_qs = dialogue.participants.exclude(id=getattr(actor, "id", None))

    for recipient in recipients_qs:
        if not _recipient_can_receive_for_message(
            message=message,
            recipient=recipient,
        ):
            continue

        if not _conversation_notification_allowed(
            recipient=recipient,
            actor=actor,
        ):
            continue

        text = f"{actor_name} pinned a message in {group_name}."

        extra_payload = {
            "dialogue_id": str(dialogue.id),
            "dialogue_slug": dialogue_slug,
            "message_id": str(message.id),
            "pin_id": str(pin.id),
            "is_group": "true",
            "message_kind": "pinned",
            "conversation_link": link,
        }

        _dispatch_after_commit(
            recipient=recipient,
            actor=actor,
            notif_type="messenger_message_pinned",
            message=text,
            link=link,
            extra_payload=extra_payload,
        )

        logger.info(
            "[MessengerNotif] Pin push queued recipient=%s actor=%s dialogue=%s message=%s",
            getattr(recipient, "id", None),
            getattr(actor, "id", None),
            getattr(dialogue, "id", None),
            getattr(message, "id", None),
        )


def _reaction_title(reaction_type: str) -> str:
    """Return a user-facing reaction title."""
    mapping = {
        "like": "Like",
        "dislike": "Dislike",
        "gratitude": "Gratitude",
        "heart": "Heart",
        "encouragement": "Encouragement",
    }

    cleaned = (reaction_type or "").strip().lower()
    return mapping.get(cleaned, cleaned.replace("_", " ").title() or "reaction")


def notify_message_reaction(
    *,
    message: Message,
    actor,
    reaction_type: str,
    reaction_action: str | None = None,
    was_removed: bool = False,
) -> None:
    """
    Push-only notification when someone reacts to a message.

    Direct chat:
    - notify the original message sender only.

    Group chat:
    - notify the original message sender only.
    - do not notify every group member to avoid notification spam.
    """
    action = (reaction_action or "").strip().lower()

    if was_removed or action in {"removed", "remove", "deleted", "delete"}:
        logger.info(
            "[MessengerNotif][Reaction] skipped_removed action=%s message=%s actor=%s",
            reaction_action,
            getattr(message, "id", None),
            getattr(actor, "id", None),
        )
        return

    if not message:
        logger.info("[MessengerNotif][Reaction] skipped_no_message")
        return

    if not actor:
        logger.info(
            "[MessengerNotif][Reaction] skipped_no_actor message=%s",
            getattr(message, "id", None),
        )
        return

    if getattr(message, "is_system", False):
        logger.info(
            "[MessengerNotif][Reaction] skipped_system_message message=%s actor=%s",
            getattr(message, "id", None),
            getattr(actor, "id", None),
        )
        return

    dialogue = getattr(message, "dialogue", None)
    recipient = getattr(message, "sender", None)

    if not dialogue:
        logger.info(
            "[MessengerNotif][Reaction] skipped_no_dialogue message=%s actor=%s",
            getattr(message, "id", None),
            getattr(actor, "id", None),
        )
        return

    if not recipient:
        logger.info(
            "[MessengerNotif][Reaction] skipped_no_recipient message=%s actor=%s dialogue=%s",
            getattr(message, "id", None),
            getattr(actor, "id", None),
            getattr(dialogue, "id", None),
        )
        return

    if getattr(recipient, "id", None) == getattr(actor, "id", None):
        logger.info(
            "[MessengerNotif][Reaction] skipped_self_reaction message=%s actor=%s",
            getattr(message, "id", None),
            getattr(actor, "id", None),
        )
        return

    if not _recipient_can_receive_for_message(
        message=message,
        recipient=recipient,
    ):
        logger.info(
            "[MessengerNotif][Reaction] skipped_recipient_cannot_receive message=%s actor=%s recipient=%s dialogue=%s",
            getattr(message, "id", None),
            getattr(actor, "id", None),
            getattr(recipient, "id", None),
            getattr(dialogue, "id", None),
        )
        return

    if not _conversation_notification_allowed(
        recipient=recipient,
        actor=actor,
    ):
        logger.info(
            "[MessengerNotif][Reaction] skipped_policy_blocked message=%s actor=%s recipient=%s dialogue=%s",
            getattr(message, "id", None),
            getattr(actor, "id", None),
            getattr(recipient, "id", None),
            getattr(dialogue, "id", None),
        )
        return

    is_group = bool(getattr(dialogue, "is_group", False))
    actor_name = _actor_display_name(actor)
    reaction_title = _reaction_title(reaction_type)
    link = _message_link(dialogue, getattr(message, "id", None))
    dialogue_slug = _dialogue_slug(dialogue) or ""

    if is_group:
        group_name = _dialogue_title(dialogue)
        notif_type = "messenger_reaction_group"
        text = f"{actor_name} reacted with {reaction_title} to your message in {group_name}."
    else:
        notif_type = "messenger_reaction_direct"
        text = f"{actor_name} reacted with {reaction_title} to your message."

    extra_payload = {
        "dialogue_id": str(dialogue.id),
        "dialogue_slug": dialogue_slug,
        "message_id": str(message.id),
        "is_group": str(is_group).lower(),
        "message_kind": "reaction",
        "reaction_type": str(reaction_type or ""),
        "reaction_action": action or "created",
        "conversation_link": link,
    }

    _dispatch_after_commit(
        recipient=recipient,
        actor=actor,
        notif_type=notif_type,
        message=text,
        link=link,
        extra_payload=extra_payload,
    )
