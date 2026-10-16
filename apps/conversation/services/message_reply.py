# apps/conversation/services/message_reply.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

import base64

from apps.conversation.models import Message
from apps.conversation.policies import (
    ConversationSecurityMode,
    ConversationSecurityPolicy,
)


def _reply_error(code: str, message: str):
    """Build a stable reply validation error."""
    return {
        "ok": False,
        "code": code,
        "message": message,
    }


def _reply_success(message_obj):
    """Build a stable reply validation success payload."""
    return {
        "ok": True,
        "message_obj": message_obj,
    }


def validate_reply_target(*, dialogue, acting_user, reply_to_message_id):
    """
    Validate reply target for both DM and group messages.

    Rules:
    - empty value is allowed
    - target must exist
    - target must belong to same dialogue
    - target must be visible to acting user
    - target must not be a system message
    """
    if not reply_to_message_id:
        return _reply_success(None)

    try:
        target = Message.objects.select_related("dialogue", "sender").get(id=reply_to_message_id)
    except Message.DoesNotExist:
        return _reply_error("REPLY_TARGET_NOT_FOUND", "Reply target message not found.")

    if target.dialogue_id != dialogue.id:
        return _reply_error("INVALID_REPLY_TARGET", "Reply target must belong to the same dialogue.")

    if not (
        dialogue.visible_messages_for_user(acting_user)
        .filter(id=target.id)
        .exists()
    ):
        return _reply_error(
            "INVALID_REPLY_TARGET",
            "Reply target is not visible to you.",
        )

    if target.is_system:
        return _reply_error("INVALID_REPLY_TARGET", "System messages cannot be used as reply targets.")

    return _reply_success(target)


def _reply_sender_payload(target):
    attribution = getattr(target, "organization_attribution", None)
    if attribution is not None:
        organization = attribution.organization
        return {
            "sender": None,
            "sender_type": "organization",
            "organization_sender": {
                "public_id": str(organization.public_id),
                "slug": organization.slug,
                "name": organization.name,
            },
        }

    return {
        "sender": {
            "id": target.sender.id,
            "username": target.sender.username,
            "email": target.sender.email,
        },
        "sender_type": "user",
        "organization_sender": None,
    }


def build_reply_preview(*, message, acting_user=None):
    """Build a visibility-safe preview for all Conversation contexts."""
    target = getattr(message, "reply_to", None)
    if not target:
        return None

    if acting_user and not (
        target.dialogue
        .visible_messages_for_user(acting_user)
        .filter(id=target.id)
        .exists()
    ):
        return None

    sender_payload = _reply_sender_payload(target)
    preview = {
        "id": target.id,
        "dialogue_slug": target.dialogue.slug,
        **sender_payload,
        "timestamp": target.timestamp.isoformat(),
        "is_system": bool(target.is_system),
        "system_event": target.system_event,
        "is_deleted": False,
        "has_file": bool(target.image or target.video or target.audio or target.file),
        "file_type": None,
        "is_encrypted": bool(target.encryptions.exists()),
        "content": None,
        "decrypted_content": None,
    }

    if target.image:
        preview["file_type"] = "image"
    elif target.video:
        preview["file_type"] = "video"
    elif target.audio:
        preview["file_type"] = "audio"
    elif target.file:
        preview["file_type"] = "file"

    security = ConversationSecurityPolicy.resolve(target.dialogue)
    if security.mode == ConversationSecurityMode.BACKEND_MANAGED:
        raw = target.content_encrypted
        if raw:
            try:
                if isinstance(raw, memoryview):
                    raw = raw.tobytes()
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", errors="ignore")

                plain = base64.b64decode(raw).decode("utf-8")
                preview["content"] = plain
                preview["decrypted_content"] = plain
            except Exception:
                preview["content"] = None
                preview["decrypted_content"] = None

    return preview
