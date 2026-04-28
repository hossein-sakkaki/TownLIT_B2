# apps/conversation/services/read_delivery.py

from apps.conversation.models import Dialogue, Message


def _error(code: str, message: str, status_code: int):
    """Build a stable service error payload."""
    return {
        "ok": False,
        "code": code,
        "message": message,
        "status": status_code,
    }


def _success(payload: dict):
    """Build a stable service success payload."""
    return {
        "ok": True,
        "payload": payload,
    }


def _get_dialogue_for_user(dialogue_slug, user):
    """Load dialogue only if user is a participant."""
    if not dialogue_slug:
        return None

    return Dialogue.objects.filter(
        slug=dialogue_slug,
        participants=user,
    ).first()


def _get_message_for_dialogue(dialogue, message_id):
    """Load message only inside the given dialogue."""
    if not dialogue or not message_id:
        return None

    return Message.objects.filter(
        id=message_id,
        dialogue=dialogue,
    ).first()


def _mark_message_delivered_sync(message):
    """Persist delivered state in sync ORM code."""
    if not message.is_delivered:
        message.is_delivered = True
        message.save(update_fields=["is_delivered"])


def _mark_message_read_sync(message, user):
    """Persist read state in sync ORM code."""
    if user == message.sender:
        return

    if not message.seen_by_users.filter(id=user.id).exists():
        message.seen_by_users.add(user)



def build_mark_as_read_realtime_payload(payload: dict) -> dict:
    """
    Build canonical realtime payload for mark_as_read event.
    """
    return {
        "dialogue_slug": payload["dialogue_slug"],
        "reader": payload["reader"],
        "read_messages": payload["read_messages"],
    }


def build_unread_count_snapshot_payload(results: list[dict]) -> dict:
    """
    Build canonical realtime payload for unread snapshot event.
    """
    return {
        "mode": "snapshot",
        "payload": results,
    }


def mark_message_delivered_for_user(dialogue_slug, message_id, acting_user):
    """
    Mark one message as delivered by recipient.
    Shared by API and WebSocket flows.
    """
    if not dialogue_slug or not message_id:
        return _error(
            "BAD_REQUEST",
            "dialogue_slug and message_id are required.",
            400,
        )

    dialogue = _get_dialogue_for_user(dialogue_slug, acting_user)
    if not dialogue:
        return _error(
            "NOT_FOUND",
            "Dialogue not found.",
            404,
        )

    message = _get_message_for_dialogue(dialogue, message_id)
    if not message:
        return _error(
            "NOT_FOUND",
            "Message not found.",
            404,
        )

    if message.sender_id == acting_user.id:
        return _error(
            "FORBIDDEN",
            "Sender cannot acknowledge delivery.",
            403,
        )

    _mark_message_delivered_sync(message)

    return _success({
        "dialogue_slug": dialogue.slug,
        "message_id": message.id,
        "user_id": acting_user.id,
        "sender_id": message.sender_id,
        "is_delivered": True,
    })


def mark_dialogue_read_for_user(dialogue_slug, acting_user):
    """
    Mark all visible incoming unread messages as read for this user.
    Shared by API and WebSocket flows.
    """
    if not dialogue_slug:
        return _error(
            "BAD_REQUEST",
            "dialogue_slug is required.",
            400,
        )

    dialogue = _get_dialogue_for_user(dialogue_slug, acting_user)
    if not dialogue:
        return _error(
            "NOT_FOUND",
            "Dialogue not found.",
            404,
        )

    unread_messages = list(
        Message.objects.filter(dialogue=dialogue)
        .exclude(seen_by_users=acting_user)
        .exclude(sender=acting_user)
        .exclude(deleted_by_users=acting_user)
    )

    read_message_ids = []

    for message in unread_messages:
        _mark_message_read_sync(message, acting_user)
        read_message_ids.append(message.id)

    payload = {
        "dialogue_slug": dialogue.slug,
        "reader": {
            "id": acting_user.id,
            "username": acting_user.username,
            "email": acting_user.email,
        },
        "read_messages": read_message_ids,
    }

    return _success(payload)