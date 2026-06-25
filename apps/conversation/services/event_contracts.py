# apps/conversation/services/event_contracts.py

from __future__ import annotations

from typing import Any

from apps.conversation.services.message_media_descriptors import (
    build_message_media_descriptors,
)

def build_sender_data(user) -> dict:
    """
    Canonical sender shape for conversation realtime events.
    """
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
    }


# -------------------------------------------------------------------
# Chat message events
# -------------------------------------------------------------------
def build_group_chat_message_data(*, message, plain_text: str, reply_preview=None, forward_preview=None) -> dict:
    """
    Canonical realtime payload for one plaintext group message.
    """
    return {
        "message_id": message.id,
        "dialogue_slug": message.dialogue.slug,
        "content": plain_text,
        "decrypted_content": plain_text,
        "sender": build_sender_data(message.sender),
        "timestamp": message.timestamp.isoformat(),
        "is_encrypted": False,
        "encrypted_for_device": None,
        "reply_to_message_id": message.reply_to_id,
        "reply_preview": reply_preview,
        "is_forwarded": bool(message.is_forwarded),
        "forwarded_from_message_id": message.forwarded_from_id,
        "forward_preview": forward_preview,
    }


def build_dm_chat_message_data(
    *,
    message,
    encrypted_content: str,
    device_id: str,
    reply_preview=None,
    forward_preview=None,
) -> dict:
    """
    Canonical realtime payload for one encrypted DM message to one device.
    """
    return {
        "message_id": message.id,
        "dialogue_slug": message.dialogue.slug,
        "content": encrypted_content,
        "sender": build_sender_data(message.sender),
        "timestamp": message.timestamp.isoformat(),
        "is_encrypted": True,
        "encrypted_for_device": device_id,
        "is_delivered": False,
        "reply_to_message_id": message.reply_to_id,
        "reply_preview": reply_preview,
        "is_forwarded": bool(message.is_forwarded),
        "forwarded_from_message_id": message.forwarded_from_id,
        "forward_preview": forward_preview,
    }


def build_system_chat_message_data(
    *,
    dialogue,
    system_message,
    sender,
    plain_text: str,
    system_event: str,
) -> dict:
    """
    Canonical realtime payload for one system message.
    """
    return {
        "event_type": "system_message",
        "dialogue_slug": dialogue.slug,
        "message_id": system_message.id,
        "decrypted_content": plain_text,
        "content": plain_text,
        "sender": {
            "id": sender.id,
            "username": sender.username,
        },
        "timestamp": system_message.timestamp.isoformat(),
        "is_system": True,
        "system_event": system_event,
        "is_encrypted": False,
    }


# -------------------------------------------------------------------
# Edit events
# -------------------------------------------------------------------
def build_group_edit_message_data(*, payload: dict) -> dict:
    """
    Canonical realtime payload for group message edit.
    """
    return {
        "message_id": payload["message_id"],
        "dialogue_slug": payload["dialogue_slug"],
        "new_content": payload["new_content"],
        "content": payload["new_content"],
        "decrypted_content": payload["new_content"],
        "edited_at": payload["edited_at"],
        "is_encrypted": False,
        "is_edited": payload["is_edited"],
        "sender": {
            "id": payload["sender"]["id"],
            "username": payload["sender"]["username"],
        },
    }


def build_dm_edit_message_data(*, payload: dict, device_id: str, encrypted_content: str) -> dict:
    """
    Canonical realtime payload for DM message edit to one device.
    """
    return {
        "message_id": payload["message_id"],
        "dialogue_slug": payload["dialogue_slug"],
        "edited_at": payload["edited_at"],
        "is_encrypted": True,
        "is_edited": payload["is_edited"],
        "encrypted_contents": [
            {
                "device_id": device_id,
                "encrypted_content": encrypted_content,
            }
        ],
        "sender": {
            "id": payload["sender"]["id"],
            "username": payload["sender"]["username"],
        },
    }


# -------------------------------------------------------------------
# Delivery / read / unread
# -------------------------------------------------------------------
def build_delivery_event_data(*, dialogue_slug: str, message_id: int, user_id: int, is_delivered: bool = True) -> dict:
    """
    Canonical realtime payload for delivery update.
    """
    return {
        "dialogue_slug": dialogue_slug,
        "message_id": message_id,
        "user_id": user_id,
        "is_delivered": is_delivered,
    }


def build_read_event_data(*, payload: dict) -> dict:
    """
    Canonical realtime payload for read update.
    Service payload is already close to final shape, so we normalize lightly.
    """
    return {
        "dialogue_slug": payload["dialogue_slug"],
        "reader": payload["reader"],
        "read_messages": payload.get("read_messages", []),
    }


def build_unread_snapshot_event_data(*, results: list[dict]) -> dict:
    """
    Canonical realtime payload for unread snapshot.
    """
    return {
        "mode": "snapshot",
        "payload": results,
    }


def build_unread_incremental_event_data(*, dialogue_slug: str, sender_id: int, unread_count: int = 1) -> dict:
    """
    Canonical realtime payload for one incremental unread update.
    Keeps current frontend-compatible payload shape.
    """
    return {
        "payload": [
            {
                "dialogue_slug": dialogue_slug,
                "unread_count": unread_count,
                "sender_id": sender_id,
            }
        ]
    }


def build_soft_delete_event_data(*, dialogue_slug: str, message_id: int, user_id: int) -> dict:
    """
    Canonical realtime payload for soft delete.
    """
    return {
        "dialogue_slug": dialogue_slug,
        "message_id": message_id,
        "user_id": user_id,
    }


def build_hard_delete_event_data(*, dialogue_slug: str, message_id: int) -> dict:
    """
    Canonical realtime payload for hard delete.
    """
    return {
        "dialogue_slug": dialogue_slug,
        "message_id": message_id,
    }


# -------------------------------------------------------------------
# Typing / recording / upload
# -------------------------------------------------------------------
def build_typing_status_event_data(*, dialogue_slug: str, user) -> dict:
    """
    Canonical realtime payload for typing status.
    """
    return {
        "dialogue_slug": dialogue_slug,
        "sender": build_sender_data(user),
    }


def build_recording_status_event_data(*, dialogue_slug: str, user, file_type: str, is_recording: bool) -> dict:
    """
    Canonical realtime payload for recording status.
    """
    return {
        "dialogue_slug": dialogue_slug,
        "sender": build_sender_data(user),
        "is_recording": is_recording,
        "file_type": file_type,
    }


def build_file_upload_status_event_data(
    *,
    dialogue_slug: str,
    user,
    file_type: str,
    status: str,
    progress: Any = None,
) -> dict:
    """
    Canonical realtime payload for file upload status.
    """
    return {
        "dialogue_slug": dialogue_slug,
        "sender": build_sender_data(user),
        "file_type": file_type,
        "status": status,
        "progress": progress,
    }


def build_upload_canceled_event_data(*, dialogue_slug: str, file_type: str) -> dict:
    """
    Canonical realtime payload for upload canceled.
    """
    return {
        "dialogue_slug": dialogue_slug,
        "file_type": file_type,
        "status": "cancelled",
        "progress": 0,
    }


# -------------------------------------------------------------------
# File message
# -------------------------------------------------------------------
def build_file_message_event_data(
    *,
    message,
    dialogue_slug: str,
    file_type: str,
    file_url: str | None = None,
    reply_preview=None,
    forward_preview=None,
) -> dict:
    """
    Canonical realtime payload for file_message.

    Keeps legacy file_url for backward compatibility and adds Asset Delivery
    descriptors for new clients.
    """
    is_group = bool(message.dialogue.is_group)
    is_encrypted_file = bool(getattr(message, "is_encrypted_file", False))

    data = {
        "message_id": message.id,
        "dialogue_slug": dialogue_slug,
        "file_type": file_type,
        "sender": build_sender_data(message.sender),
        "timestamp": message.timestamp.isoformat(),
        "is_encrypted_file": is_encrypted_file,
        "is_encrypted": not is_group,
        "has_file": True,
        "reply_to_message_id": message.reply_to_id,
        "reply_preview": reply_preview,
        "is_forwarded": bool(message.is_forwarded),
        "forwarded_from_message_id": message.forwarded_from_id,
        "forward_preview": forward_preview,
    }

    if file_url and not is_encrypted_file:
        data["file_url"] = file_url

    data.update(build_message_media_descriptors(message))

    return data


# -------------------------------------------------------------------
# Group/system events
# -------------------------------------------------------------------
def build_group_added_event_data(*, dialogue: dict) -> dict:
    return {
        "dialogue": dialogue,
    }


def build_group_removed_event_data(*, dialogue: dict) -> dict:
    return {
        "dialogue": dialogue,
    }


def build_group_left_event_data(*, user: dict, dialogue_slug: str) -> dict:
    return {
        "user": user,
        "dialogue_slug": dialogue_slug,
    }


def build_founder_transferred_event_data(*, dialogue_slug: str, new_founder_id: int) -> dict:
    return {
        "dialogue_slug": dialogue_slug,
        "new_founder_id": new_founder_id,
    }
    
    
# -------------------------------------------------------------------
# Message pin events
# -------------------------------------------------------------------
def build_message_pin_event_data(*, pin) -> dict:
    """
    Canonical realtime payload for message pin create/update.
    """
    return {
        "pin_id": pin.id,
        "dialogue_slug": pin.dialogue.slug,
        "message_id": pin.message_id,
        "position": pin.position,
        "pinned_by": build_sender_data(pin.pinned_by),
        "pin_duration": pin.pin_duration,
        "expires_at": pin.expires_at.isoformat() if pin.expires_at else None,
        "reminders_enabled": bool(pin.reminders_enabled),
        "created_at": pin.created_at.isoformat(),
    }


def build_message_unpin_event_data(*, dialogue_slug: str, message_id: int) -> dict:
    """
    Canonical realtime payload for message unpin.
    """
    return {
        "dialogue_slug": dialogue_slug,
        "message_id": message_id,
    }
    

# -------------------------------------------------------------------
# Dialogue pin events
# -------------------------------------------------------------------
def build_dialogue_pinned_event_data(*, dialogue: dict) -> dict:
    """
    Canonical realtime payload for dialogue pin.
    """
    return {
        "dialogue": dialogue,
    }


def build_dialogue_unpinned_event_data(*, dialogue: dict) -> dict:
    """
    Canonical realtime payload for dialogue unpin.
    """
    return {
        "dialogue": dialogue,
    }
    
    
# -------------------------------------------------------------------
# Message reaction events
# -------------------------------------------------------------------
def build_message_reaction_summary_event_data(*, dialogue_slug: str, summary: dict) -> dict:
    """
    Canonical realtime payload for message reaction summary update.
    """
    return {
        "dialogue_slug": dialogue_slug,
        "summary": summary,
    }


def build_message_reaction_toggled_event_data(
    *,
    dialogue_slug: str,
    message_id: int,
    user_id: int,
    reaction_type: str | None,
    action: str,
    summary: dict,
) -> dict:
    """
    Canonical realtime payload for message reaction toggle.
    """
    return {
        "dialogue_slug": dialogue_slug,
        "message_id": message_id,
        "user_id": user_id,
        "reaction_type": reaction_type,
        "action": action,
        "summary": summary,
    }
    
# -------------------------------------------------------------------
# Group events
# -------------------------------------------------------------------
def build_group_updated_event_data(
    *,
    dialogue_slug: str,
    reason: str,
    dialogue: dict | None = None,
    actor_id: int | None = None,
    target_user_id: int | None = None,
) -> dict:
    """
    Canonical lightweight group sync event.

    This event tells clients:
    - this group changed
    - refresh local dialogue/member/avatar state
    - optionally apply the embedded dialogue snapshot immediately
    """
    payload = {
        "dialogue_slug": dialogue_slug,
        "reason": reason,
    }

    if dialogue is not None:
        payload["dialogue"] = dialogue

    if actor_id is not None:
        payload["actor_id"] = actor_id

    if target_user_id is not None:
        payload["target_user_id"] = target_user_id

    return payload