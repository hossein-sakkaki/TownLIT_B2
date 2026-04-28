# apps/conversation/services/message_reactions.py

from collections import defaultdict

from django.db import transaction

from apps.conversation.models import Message, MessageReaction
from apps.conversation.constants import (
    MSG_LIKE,
    MSG_DISLIKE,
    MSG_GRATITUDE,
    MSG_HEART,
    MSG_ENCOURAGEMENT,
)


ALLOWED_MESSAGE_REACTIONS = {
    MSG_LIKE,
    MSG_DISLIKE,
    MSG_GRATITUDE,
    MSG_HEART,
    MSG_ENCOURAGEMENT,
}


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


def _is_message_visible_to_user(message, user) -> bool:
    """Check whether a message is visible to the acting user."""
    if not message.dialogue.participants.filter(id=user.id).exists():
        return False
    if message.deleted_by_users.filter(id=user.id).exists():
        return False
    return True


def _validate_reaction_type(reaction_type: str):
    """Validate reaction type against messenger-specific set."""
    normalized = (reaction_type or "").strip().lower()
    if normalized not in ALLOWED_MESSAGE_REACTIONS:
        return None
    return normalized


def build_message_reaction_summary(*, message, acting_user=None):
    """
    Build canonical reaction summary for one message.

    Shape:
    {
        "message_id": ...,
        "total_count": ...,
        "counts": {
            "like": 2,
            ...
        },
        "items": [
            {"reaction_type": "like", "count": 2},
            ...
        ],
        "my_reaction": "heart" | None,
    }
    """
    reactions = list(
        message.message_reactions
        .select_related("user")
        .values("reaction_type", "user_id")
    )

    counter = defaultdict(int)
    my_reaction = None

    for row in reactions:
        reaction_type = row["reaction_type"]
        user_id = row["user_id"]
        counter[reaction_type] += 1

        if acting_user and getattr(acting_user, "id", None) == user_id:
            my_reaction = reaction_type

    ordered_types = [
        MSG_LIKE,
        MSG_DISLIKE,
        MSG_GRATITUDE,
        MSG_HEART,
        MSG_ENCOURAGEMENT,
    ]

    items = []
    total_count = 0

    for reaction_type in ordered_types:
        count = counter.get(reaction_type, 0)
        if count <= 0:
            continue

        items.append({
            "reaction_type": reaction_type,
            "count": count,
        })
        total_count += count

    return {
        "message_id": message.id,
        "total_count": total_count,
        "counts": {key: counter.get(key, 0) for key in ordered_types},
        "items": items,
        "my_reaction": my_reaction,
    }


def toggle_message_reaction(*, message_id, acting_user, reaction_type):
    """
    Toggle or replace one user's reaction on one message.

    Rules:
    - one active reaction per user per message
    - same reaction => remove
    - different reaction => replace
    """
    normalized_type = _validate_reaction_type(reaction_type)
    if not normalized_type:
        return _error("INVALID_REACTION_TYPE", "Invalid reaction type.", 400)

    try:
        message = Message.objects.select_related("dialogue", "sender").get(id=message_id)
    except Message.DoesNotExist:
        return _error("MESSAGE_NOT_FOUND", "Message not found.", 404)

    if not _is_message_visible_to_user(message, acting_user):
        return _error("FORBIDDEN", "You cannot react to this message.", 403)

    if message.is_system:
        return _error("INVALID_TARGET", "System messages cannot receive reactions.", 400)

    with transaction.atomic():
        existing = MessageReaction.objects.filter(
            message=message,
            user=acting_user,
        ).first()

        action = None

        if existing and existing.reaction_type == normalized_type:
            existing.delete()
            action = "removed"
        elif existing:
            existing.reaction_type = normalized_type
            existing.save(update_fields=["reaction_type", "updated_at"])
            action = "replaced"
        else:
            MessageReaction.objects.create(
                message=message,
                user=acting_user,
                reaction_type=normalized_type,
            )
            action = "added"

    summary = build_message_reaction_summary(
        message=message,
        acting_user=acting_user,
    )

    return _success({
        "message": message,
        "action": action,
        "reaction_type": normalized_type,
        "summary": summary,
    })


def get_message_reaction_summary_for_user(*, message_id, acting_user):
    """Return reaction summary for one visible message."""
    try:
        message = Message.objects.select_related("dialogue").get(id=message_id)
    except Message.DoesNotExist:
        return _error("MESSAGE_NOT_FOUND", "Message not found.", 404)

    if not _is_message_visible_to_user(message, acting_user):
        return _error("FORBIDDEN", "You cannot access this message.", 403)

    summary = build_message_reaction_summary(
        message=message,
        acting_user=acting_user,
    )

    return _success({
        "message": message,
        "summary": summary,
    })


def list_message_reactors(*, message_id, acting_user):
    """
    Return detailed reactor list for one message.

    Can be useful for future modal/details UI.
    """
    try:
        message = Message.objects.select_related("dialogue").get(id=message_id)
    except Message.DoesNotExist:
        return _error("MESSAGE_NOT_FOUND", "Message not found.", 404)

    if not _is_message_visible_to_user(message, acting_user):
        return _error("FORBIDDEN", "You cannot access this message.", 403)

    rows = list(
        message.message_reactions
        .select_related("user")
        .order_by("reaction_type", "created_at")
    )

    reactors = [
        {
            "user_id": row.user_id,
            "username": row.user.username,
            "email": row.user.email,
            "reaction_type": row.reaction_type,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]

    return _success({
        "message": message,
        "reactors": reactors,
        "count": len(reactors),
    })