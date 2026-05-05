# apps/conversation/services/message_creation.py

import base64
import json

from django.db import transaction

from apps.conversation.models import Dialogue, Message, MessageEncryption
from common.mime_type_validator import validate_file_type, is_unsafe_file
from apps.conversation.services.message_reply import validate_reply_target

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
        device_id = str(item.get("device_id") or "").strip().lower()
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


def _normalize_encrypted_keys_mapping(raw_value):
    """
    Normalize encrypted per-device AES keys.
    Accepts:
        - dict: {device_id: encrypted_key}
        - JSON string of the same dict
    Returns:
        - list[{"device_id": "...", "encrypted_content": "..."}]
    """
    if not raw_value:
        return []

    payload = raw_value

    if isinstance(raw_value, str):
        try:
            payload = json.loads(raw_value)
        except Exception:
            return []

    if not isinstance(payload, dict):
        return []

    seen = set()
    clean_items = []

    for device_id, encrypted_key in payload.items():
        norm_device_id = str(device_id or "").strip().lower()

        if not norm_device_id or not isinstance(encrypted_key, str) or not encrypted_key:
            continue

        if norm_device_id in seen:
            continue

        seen.add(norm_device_id)
        clean_items.append({
            "device_id": norm_device_id,
            "encrypted_content": encrypted_key,
        })

    return clean_items


def _decode_aes_key_bytes(raw_value):
    """
    Decode base64 AES key from request value.
    """
    if not raw_value:
        return None

    try:
        return base64.b64decode(str(raw_value).encode("utf-8"))
    except Exception:
        return None


def prepare_encrypted_file_request(
    *,
    is_encrypted_file,
    encrypted_for_device=None,
    aes_key_encrypted=None,
    encrypted_keys_per_device=None,
):
    """
    Normalize encrypted file request fields for create_file_message.
    Used by API layer so the service remains the source of truth.
    """
    normalized = {
        "is_encrypted_file": bool(is_encrypted_file),
        "encrypted_for_device": str(encrypted_for_device or "").strip().lower(),
        "aes_key_encrypted_bytes": None,
        "encrypted_keys_per_device": [],
    }

    if not normalized["is_encrypted_file"]:
        return _success(normalized)

    aes_key_bytes = _decode_aes_key_bytes(aes_key_encrypted)
    if not aes_key_bytes:
        return _error(
            "BAD_REQUEST",
            "Invalid or missing aes_key_encrypted.",
            400,
        )

    normalized["aes_key_encrypted_bytes"] = aes_key_bytes
    normalized["encrypted_keys_per_device"] = _normalize_encrypted_keys_mapping(
        encrypted_keys_per_device
    )

    return _success(normalized)


def create_text_message(
    *,
    dialogue,
    sender,
    is_encrypted,
    content=None,
    encrypted_contents=None,
    recipient_hidden_on_incoming=False,
    recipient=None,
    reply_to_message_id=None,
):
    """
    Create one text message in a shared backend service path.
    Supports:
    - Group plaintext messages
    - DM encrypted messages
    """
    
    reply_validation = validate_reply_target(
        dialogue=dialogue,
        acting_user=sender,
        reply_to_message_id=reply_to_message_id,
    )
    if not reply_validation.get("ok"):
        return _error(
            reply_validation["code"],
            reply_validation["message"],
            400,
        )

    reply_to_message = reply_validation["message_obj"]
    
    if dialogue.is_group:
        if is_encrypted:
            return _error("BAD_REQUEST", "Group messages should not be encrypted.", 400)

        plain_text = (content or "").strip()
        if not plain_text:
            return _error("BAD_REQUEST", "Message content is required for group chat.", 400)

        base64_str = base64.b64encode(plain_text.encode("utf-8")).decode("utf-8")
        content_bytes = base64_str.encode("utf-8")

        message = Message.objects.create(
            dialogue=dialogue,
            sender=sender,
            content_encrypted=content_bytes,
            reply_to=reply_to_message,
        )

        dialogue.last_message = message
        dialogue.save(update_fields=["last_message"])

        return _success({
            "message": message,
            "dialogue_slug": dialogue.slug,
            "message_id": message.id,
            "is_group": True,
            "is_encrypted": False,
            "reply_to_message_id": reply_to_message.id if reply_to_message else None,
        })

    # DM flow
    if not is_encrypted:
        return _error("BAD_REQUEST", "DM messages must be encrypted on client.", 400)

    clean_items = _normalize_encrypted_contents(encrypted_contents)
    if not clean_items:
        return _error("BAD_REQUEST", "encrypted_contents must be a non-empty valid list.", 400)

    with transaction.atomic():
        message = Message.objects.create(
            dialogue=dialogue,
            sender=sender,
            content_encrypted=b"[Encrypted]",
            reply_to=reply_to_message,
        )

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

        if recipient_hidden_on_incoming and recipient:
            message.deleted_by_users.add(recipient)

        dialogue.last_message = message
        dialogue.save(update_fields=["last_message"])

    return _success({
        "message": message,
        "dialogue_slug": dialogue.slug,
        "message_id": message.id,
        "is_group": False,
        "is_encrypted": True,
        "encrypted_contents": clean_items[:500],
        "reply_to_message_id": reply_to_message.id if reply_to_message else None,
    })


def validate_upload_input(*, uploaded_file, max_file_size=1000 * 1024 * 1024):
    """
    Validate uploaded file and resolve target model field.
    """
    if not uploaded_file:
        return _error("BAD_REQUEST", "File is required.", 400)

    if uploaded_file.size > max_file_size:
        return _error("BAD_REQUEST", "File too large. Max size is 1000MB.", 400)

    file_name = (uploaded_file.name or "").lower()
    file_type = uploaded_file.content_type or "application/octet-stream"

    if is_unsafe_file(file_name):
        return _error(
            "BAD_REQUEST",
            "This file type is not allowed for security reasons.",
            400,
        )

    field_name = validate_file_type(file_name, file_type)
    if not field_name:
        return _error(
            "BAD_REQUEST",
            f"Unsupported file type: {file_type}",
            400,
        )

    return _success({
        "field_name": field_name,
        "file_name": file_name,
        "file_type": file_type,
    })


def create_file_message(
    *,
    dialogue,
    sender,
    uploaded_file,
    field_name,
    is_encrypted_file,
    encrypted_for_device=None,
    aes_key_encrypted_bytes=None,
    encrypted_keys_per_device=None,
    recipient_hidden_on_incoming=False,
    recipient=None,
    reply_to_message_id=None,
    forwarded_from_message=None,
):
    """
    Create one file message in a shared backend service path.

    Supports:
    - Group non-encrypted file messages
    - DM encrypted file messages
    - Forward metadata for client-side media forwarding
    """
    reply_validation = validate_reply_target(
        dialogue=dialogue,
        acting_user=sender,
        reply_to_message_id=reply_to_message_id,
    )
    if not reply_validation.get("ok"):
        return _error(
            reply_validation["code"],
            reply_validation["message"],
            400,
        )

    reply_to_message = reply_validation["message_obj"]

    # Forward metadata is only a relation marker.
    # Actual file bytes are still created through the normal upload path.
    is_forwarded = forwarded_from_message is not None

    if dialogue.is_group:
        if is_encrypted_file:
            return _error("BAD_REQUEST", "Group files must not be client-encrypted.", 400)

        message = Message.objects.create(
            dialogue=dialogue,
            sender=sender,
            is_encrypted_file=False,
            reply_to=reply_to_message,
            is_forwarded=is_forwarded,
            forwarded_from=forwarded_from_message,
            **{field_name: uploaded_file},
        )

        dialogue.last_message = message
        dialogue.save(update_fields=["last_message"])

        return _success({
            "message": message,
            "dialogue_slug": dialogue.slug,
            "message_id": message.id,
            "is_group": True,
            "is_encrypted_file": False,
            "field_name": field_name,
            "reply_to_message_id": reply_to_message.id if reply_to_message else None,
            "is_forwarded": is_forwarded,
            "forwarded_from_message_id": forwarded_from_message.id if forwarded_from_message else None,
        })

    # DM flow
    if not is_encrypted_file:
        return _error("BAD_REQUEST", "DM file uploads must be end-to-end encrypted.", 400)

    if not aes_key_encrypted_bytes or not encrypted_for_device:
        return _error(
            "BAD_REQUEST",
            "Missing E2EE fields: aes_key_encrypted and encrypted_for_device.",
            400,
        )

    clean_items = _normalize_encrypted_contents(encrypted_keys_per_device or [])

    with transaction.atomic():
        message = Message.objects.create(
            dialogue=dialogue,
            sender=sender,
            is_encrypted_file=True,
            encrypted_for_device=encrypted_for_device,
            aes_key_encrypted=aes_key_encrypted_bytes,
            reply_to=reply_to_message,
            is_forwarded=is_forwarded,
            forwarded_from=forwarded_from_message,
            **{field_name: uploaded_file},
        )

        if recipient_hidden_on_incoming and recipient:
            message.deleted_by_users.add(recipient)

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

        dialogue.last_message = message
        dialogue.save(update_fields=["last_message"])

    return _success({
        "message": message,
        "dialogue_slug": dialogue.slug,
        "message_id": message.id,
        "is_group": False,
        "is_encrypted_file": True,
        "field_name": field_name,
        "reply_to_message_id": reply_to_message.id if reply_to_message else None,
        "is_forwarded": is_forwarded,
        "forwarded_from_message_id": forwarded_from_message.id if forwarded_from_message else None,
    })