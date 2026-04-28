# apps/conversation/services/message_forward.py

import base64
import os
from datetime import timedelta

from django.core.files.base import ContentFile
from django.db import transaction

from apps.conversation.models import Dialogue, Message
from apps.conversation.services.message_reply import build_reply_preview


FORWARD_MODE_BACKEND_ASSISTED = "backend_assisted"
FORWARD_MODE_CLIENT_REENCRYPT = "client_reencrypt"


def _error(code: str, message: str, status_code: int, extra: dict | None = None):
    """Build a stable service error payload."""
    payload = {
        "ok": False,
        "code": code,
        "message": message,
        "status": status_code,
    }
    if extra:
        payload["extra"] = extra
    return payload


def _success(payload: dict):
    """Build a stable service success payload."""
    return {
        "ok": True,
        "payload": payload,
    }


def _get_message_file_field_name(message):
    """Return the active file field name for a message, if any."""
    if message.image:
        return "image"
    if message.video:
        return "video"
    if message.audio:
        return "audio"
    if message.file:
        return "file"
    return None


def _has_plaintext_content(message) -> bool:
    """Return True when message content is backend-readable plaintext."""
    return bool(message.dialogue.is_group and message.content_encrypted)


def _decode_group_plaintext(message) -> str:
    """Decode group plaintext payload safely."""
    raw = message.content_encrypted
    if not raw:
        return ""

    try:
        if isinstance(raw, memoryview):
            raw = raw.tobytes()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="ignore")
        return base64.b64decode(raw).decode("utf-8")
    except Exception:
        return ""


def _encode_group_plaintext(content: str) -> bytes:
    """Encode plaintext to current stored group format."""
    base64_str = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    return base64_str.encode("utf-8")


def _is_message_visible_to_user(message, user) -> bool:
    """Check visibility of source message for actor."""
    if not message.dialogue.participants.filter(id=user.id).exists():
        return False
    if message.deleted_by_users.filter(id=user.id).exists():
        return False
    return True


def _resolve_forward_mode(*, source_message, target_dialogue):
    """
    Resolve secure forward mode.

    Rules:
    - Only Group -> Group is backend-assisted
    - Anything involving DM requires client-side re-encryption
    """
    if source_message.dialogue.is_group and target_dialogue.is_group:
        return FORWARD_MODE_BACKEND_ASSISTED
    return FORWARD_MODE_CLIENT_REENCRYPT


def validate_forward_request(*, source_message_id, target_dialogue_slug, acting_user):
    """
    Validate source/target and resolve secure forward mode.
    """
    if not source_message_id:
        return _error("BAD_REQUEST", "source_message_id is required.", 400)

    if not target_dialogue_slug:
        return _error("BAD_REQUEST", "target_dialogue_slug is required.", 400)

    try:
        source_message = Message.objects.select_related("dialogue", "sender", "reply_to", "forwarded_from").get(
            id=source_message_id
        )
    except Message.DoesNotExist:
        return _error("SOURCE_MESSAGE_NOT_FOUND", "Source message not found.", 404)

    try:
        target_dialogue = Dialogue.objects.get(
            slug=target_dialogue_slug,
            participants=acting_user,
        )
    except Dialogue.DoesNotExist:
        return _error("TARGET_DIALOGUE_NOT_FOUND", "Target dialogue not found.", 404)

    if not _is_message_visible_to_user(source_message, acting_user):
        return _error("FORBIDDEN", "Source message is not visible to you.", 403)

    if source_message.is_system:
        return _error("INVALID_FORWARD_SOURCE", "System messages cannot be forwarded.", 400)

    mode = _resolve_forward_mode(
        source_message=source_message,
        target_dialogue=target_dialogue,
    )

    return _success({
        "source_message": source_message,
        "target_dialogue": target_dialogue,
        "forward_mode": mode,
    })


def _copy_file_field_from_source(*, source_message, target_message):
    """
    Copy stored source file bytes into a new message file field.

    Notes:
    - Used only for backend-assisted Group -> Group forwarding.
    - Does not reuse DB row or mutate the source message.
    """
    field_name = _get_message_file_field_name(source_message)
    if not field_name:
        return None

    src_field = getattr(source_message, field_name, None)
    if not src_field:
        return None

    src_name = getattr(src_field, "name", None)
    if not src_name:
        return None

    with src_field.open("rb") as fh:
        file_bytes = fh.read()

    original_name = os.path.basename(src_name) or f"forwarded-{source_message.id}"
    generated_name = f"fwd-{source_message.id}-{original_name}"

    getattr(target_message, field_name).save(
        generated_name,
        ContentFile(file_bytes),
        save=False,
    )

    return field_name


def build_forward_preview(*, message):
    """
    Build safe forward preview metadata from source relation.

    Group:
    - plaintext preview may be exposed

    DM:
    - plaintext preview must not be exposed
    """
    source = getattr(message, "forwarded_from", None)
    if not source:
        return None

    preview = {
        "id": source.id,
        "dialogue_slug": source.dialogue.slug,
        "sender": {
            "id": source.sender.id,
            "username": source.sender.username,
            "email": source.sender.email,
        },
        "timestamp": source.timestamp.isoformat(),
        "is_system": bool(source.is_system),
        "is_deleted": False,
        "has_file": bool(source.image or source.video or source.audio or source.file),
        "file_type": _get_message_file_field_name(source),
        "is_encrypted": bool(source.encryptions.exists()),
        "content": None,
        "decrypted_content": None,
    }

    if source.dialogue.is_group:
        plain = _decode_group_plaintext(source)
        if plain:
            preview["content"] = plain
            preview["decrypted_content"] = plain

    return preview


def create_forwarded_message_backend_assisted(*, source_message_id, target_dialogue_slug, acting_user):
    """
    Backend-assisted forward.

    Supported now:
    - Group -> Group only

    Not supported now:
    - Any forward touching DM/E2EE
    """
    validation = validate_forward_request(
        source_message_id=source_message_id,
        target_dialogue_slug=target_dialogue_slug,
        acting_user=acting_user,
    )

    if not validation.get("ok"):
        return validation

    source_message = validation["payload"]["source_message"]
    target_dialogue = validation["payload"]["target_dialogue"]
    forward_mode = validation["payload"]["forward_mode"]

    if forward_mode != FORWARD_MODE_BACKEND_ASSISTED:
        return _error(
            "SECURE_FORWARD_REQUIRES_CLIENT_REENCRYPT",
            "This forward target requires client-side decrypt and re-encrypt.",
            409,
            extra={
                "forward_mode": forward_mode,
                "source_message_id": source_message.id,
                "target_dialogue_slug": target_dialogue.slug,
            },
        )

    with transaction.atomic():
        # Forward plaintext text message
        if _has_plaintext_content(source_message):
            plain_text = _decode_group_plaintext(source_message)

            forwarded = Message.objects.create(
                dialogue=target_dialogue,
                sender=acting_user,
                content_encrypted=_encode_group_plaintext(plain_text),
                reply_to=None,
                is_forwarded=True,
                forwarded_from=source_message,
            )

            target_dialogue.last_message = forwarded
            target_dialogue.save(update_fields=["last_message"])

            return _success({
                "message": forwarded,
                "dialogue": target_dialogue,
                "message_id": forwarded.id,
                "dialogue_slug": target_dialogue.slug,
                "is_group": bool(target_dialogue.is_group),
                "is_forwarded": True,
                "forward_mode": forward_mode,
                "kind": "text",
            })

        # Forward file message
        target_message = Message(
            dialogue=target_dialogue,
            sender=acting_user,
            is_forwarded=True,
            forwarded_from=source_message,
            reply_to=None,
            is_encrypted_file=False,
        )

        copied_field = _copy_file_field_from_source(
            source_message=source_message,
            target_message=target_message,
        )

        if not copied_field:
            return _error(
                "INVALID_FORWARD_SOURCE",
                "Unsupported forward source. Message has no forwardable content.",
                400,
            )

        target_message.save()

        target_dialogue.last_message = target_message
        target_dialogue.save(update_fields=["last_message"])

    return _success({
        "message": target_message,
        "dialogue": target_dialogue,
        "message_id": target_message.id,
        "dialogue_slug": target_dialogue.slug,
        "is_group": bool(target_dialogue.is_group),
        "is_forwarded": True,
        "forward_mode": forward_mode,
        "kind": "file",
        "file_field": copied_field,
    })