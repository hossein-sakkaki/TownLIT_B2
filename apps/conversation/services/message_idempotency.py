# apps/conversation/services/message_idempotency.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-17.
# Last Update by Hossein Sakkaki on 2026-10-18.
#

from __future__ import annotations

from uuid import UUID

from apps.conversation.models import Message


MESSAGE_MEDIA_FIELDS = ("image", "video", "audio", "file")


def normalize_client_request_id(value) -> UUID | None:
    if value is None:
        return None

    if isinstance(value, UUID):
        return value

    cleaned = str(value).strip()
    if not cleaned:
        return None

    try:
        return UUID(cleaned)
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("client_request_id must be a valid UUID.") from exc


def existing_message_for_client_request(*, dialogue, sender, client_request_id):
    if client_request_id is None:
        return None

    return (
        Message.objects
        .filter(
            dialogue=dialogue,
            sender=sender,
            client_request_id=client_request_id,
        )
        .select_related("dialogue", "sender", "reply_to")
        .first()
    )


def message_media_field(message) -> str | None:
    for field_name in MESSAGE_MEDIA_FIELDS:
        if getattr(message, field_name, None):
            return field_name
    return None
