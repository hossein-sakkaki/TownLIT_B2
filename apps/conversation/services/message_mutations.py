# apps/conversation/services/message_mutations.py

import base64

from django.db import transaction
from django.utils import timezone

from apps.conversation.models import Message, MessageEncryption


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


def _normalize_encrypted_contents(encrypted_contents):
    """
    Normalize and dedupe encrypted device envelopes.
    Keeps first valid entry per device_id.
    """
    if not isinstance(encrypted_contents, list):
        return []

    seen = set()
    clean_items = []

    for item in encrypted_contents:
        device_id = (str(item.get("device_id") or "").strip().lower())
        encrypted_content = item.get("encrypted_content")

        if not device_id or not isinstance(encrypted_content, str) or not encrypted_content:
            continue

        if device_id in seen:
            continue

        seen.add(device_id)
        clean_items.append({
            "device_id": device_id,
            "encrypted_content": encrypted_content,
        })

    return clean_items


def build_message_soft_deleted_realtime_payload(payload: dict) -> dict:
    """Build canonical realtime payload for soft delete."""
    return {
        "dialogue_slug": payload["dialogue_slug"],
        "message_id": payload["message_id"],
        "user_id": payload["user_id"],
    }


def edit_message_content(message_id, acting_user, new_content=None, encrypted_contents=None):
    """
    Edit a message in one shared service path.
    Used by both API and WebSocket flows.
    """
    try:
        message = Message.objects.select_related("dialogue", "sender").get(id=message_id)
    except Message.DoesNotExist:
        return _error("NOT_FOUND", "Message not found.", 404)

    if message.sender_id != acting_user.id:
        return _error("FORBIDDEN", "Only sender can edit this message.", 403)

    if not message.can_edit():
        return _error("FORBIDDEN", "You can only edit messages within 12 hours of sending.", 403)

    dialogue = message.dialogue
    now = timezone.now()

    # Group message edit: store plaintext as base64 bytes
    if dialogue.is_group:
        plain_text = (new_content or "").strip()
        if not plain_text:
            return _error("BAD_REQUEST", "Message content cannot be empty.", 400)

        base64_str = base64.b64encode(plain_text.encode("utf-8")).decode("utf-8")
        content_bytes = base64_str.encode("utf-8")

        message.content_encrypted = content_bytes
        message.edited_at = now
        message.is_edited = True
        message.encrypted_for_device = None
        message.aes_key_encrypted = None
        message.save(
            update_fields=[
                "content_encrypted",
                "edited_at",
                "is_edited",
                "encrypted_for_device",
                "aes_key_encrypted",
            ]
        )

        dialogue.last_message = message
        dialogue.save(update_fields=["last_message"])

        return _success({
            "message_id": message.id,
            "dialogue_slug": dialogue.slug,
            "edited_at": now.isoformat(),
            "is_edited": True,
            "is_group": True,
            "new_content": plain_text,
            "sender": {
                "id": message.sender.id,
                "username": message.sender.username,
                "email": message.sender.email,
            },
        })

    # DM edit: replace per-device encrypted envelopes
    clean_items = _normalize_encrypted_contents(encrypted_contents)
    if not clean_items:
        return _error("BAD_REQUEST", "Missing or invalid encrypted_contents for private chat.", 400)

    with transaction.atomic():
        MessageEncryption.objects.filter(message=message).delete()

        to_create = [
            MessageEncryption(
                message=message,
                device_id=item["device_id"],
                encrypted_content=item["encrypted_content"],
            )
            for item in clean_items[:500]
        ]
        if to_create:
            MessageEncryption.objects.bulk_create(to_create)

        message.content_encrypted = b"[Encrypted]"
        message.edited_at = now
        message.is_edited = True
        message.save(update_fields=["content_encrypted", "edited_at", "is_edited"])

        dialogue.last_message = message
        dialogue.save(update_fields=["last_message"])

    return _success({
        "message_id": message.id,
        "dialogue_slug": dialogue.slug,
        "edited_at": now.isoformat(),
        "is_edited": True,
        "is_group": False,
        "encrypted_contents": clean_items[:500],
        "sender": {
            "id": message.sender.id,
            "username": message.sender.username,
            "email": message.sender.email,
        },
    })


def soft_delete_message_for_user(message_id, acting_user):
    """
    Soft delete one message for one user.
    Used by both API and WebSocket flows.
    """
    try:
        message = Message.objects.select_related("dialogue").get(id=message_id)
    except Message.DoesNotExist:
        return _error("NOT_FOUND", "Message not found.", 404)

    if message.deleted_by_users.filter(id=acting_user.id).exists():
        return _error("BAD_REQUEST", "Message already deleted from your chat.", 400)

    message.mark_as_deleted_by_user(acting_user)

    return _success({
        "dialogue_slug": message.dialogue.slug,
        "message_id": message.id,
        "user_id": acting_user.id,
    })


def hard_delete_message_for_user(message_id, acting_user):
    """
    Hard delete one message if the acting user is allowed.
    Used by both API and WebSocket flows.
    """
    try:
        message = Message.objects.select_related("dialogue", "sender").get(id=message_id)
    except Message.DoesNotExist:
        return _error("NOT_FOUND", "Message not found.", 404)

    if not message.can_hard_delete_for_user(acting_user):
        return _error(
            "FORBIDDEN",
            "You are not allowed to permanently delete this message.",
            403,
        )

    dialogue = message.dialogue
    dialogue_slug = dialogue.slug
    deleted_message_id = message.id
    participant_ids = list(dialogue.participants.values_list("id", flat=True))

    # Delete attached files first
    if message.image:
        message.image.delete(save=False)
    if message.video:
        message.video.delete(save=False)
    if message.audio:
        message.audio.delete(save=False)
    if message.file:
        message.file.delete(save=False)

    with transaction.atomic():
        message.encryptions.all().delete()
        message.delete()

        if dialogue.last_message_id == deleted_message_id:
            dialogue.refresh_last_message_cache()

    return _success({
        "dialogue_slug": dialogue_slug,
        "message_id": deleted_message_id,
        "participant_ids": participant_ids,
    })