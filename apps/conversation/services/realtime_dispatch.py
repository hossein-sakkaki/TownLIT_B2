# apps/conversation/services/realtime_dispatch.py

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from apps.conversation.services.boundary_access import should_send_conversation_notification

APP_NAME = "conversation"


def _group_send(group_name: str, event_name: str, data: dict | None = None):
    """
    Send one canonical conversation realtime event to one channel group.
    """
    if not group_name:
        return

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": "dispatch_event",
            "app": APP_NAME,
            "event": event_name,
            "data": data or {},
        },
    )


def conv_group_send(group_name: str, event_name: str, data: dict | None = None):
    """
    Public generic wrapper for one conversation event.
    """
    _group_send(group_name, event_name, data)


def conv_multi_group_send(group_names: list[str], event_name: str, data: dict | None = None):
    """
    Broadcast one conversation event to multiple groups.
    Deduplicates group names safely.
    """
    seen = set()

    for group_name in group_names or []:
        if not group_name or group_name in seen:
            continue

        seen.add(group_name)
        _group_send(group_name, event_name, data)


# --------------------------------------------------------------------------------------
# MESSAGE REALTIME HELPERS
# --------------------------------------------------------------------------------------

def conversation_dialogue_group_name(dialogue_slug: str) -> str:
    """
    Return the canonical channel group name for one dialogue.
    Must match the group name joined by ConversationHandler.
    """
    return f"dialogue_{dialogue_slug}"


def simple_user_payload(user) -> dict:
    """
    Build the small user payload expected by iOS/Web realtime clients.
    Keep this intentionally lightweight.
    """
    return {
        "id": user.id,
        "username": getattr(user, "username", None),
        "email": getattr(user, "email", None),
        "name": getattr(user, "name", None),
        "family": getattr(user, "family", None),
        "avatar_url": getattr(user, "avatar_url", None),
        "avatar_cdn_url": getattr(user, "avatar_cdn_url", None),
        "avatar_version": getattr(user, "avatar_version", None),
        "is_verified_identity": getattr(user, "is_verified_identity", False),
        "is_townlit_verified": getattr(user, "is_townlit_verified", False),
    }


def build_group_text_message_payload(*, message, dialogue_slug: str, plain_text: str) -> dict:
    """
    Build realtime payload for a REST-created group text message.

    Group conversations are backend-managed:
    - iOS sends plaintext to REST.
    - Backend stores it according to group encryption/storage policy.
    - Backend broadcasts a readable payload to active group participants.
    """
    return {
        "message_id": message.id,
        "dialogue_slug": dialogue_slug,
        "content": plain_text,
        "decrypted_content": plain_text,
        "sender": simple_user_payload(message.sender),
        "timestamp": message.timestamp.isoformat(),
        "is_delivered": bool(getattr(message, "is_delivered", False)),
        "is_system": bool(getattr(message, "is_system", False)),
        "system_event": getattr(message, "system_event", None),
        "reply_to_message_id": message.reply_to_id,
        "reply_preview": None,
        "is_forwarded": bool(getattr(message, "is_forwarded", False)),
        "forwarded_from_message_id": getattr(message, "forwarded_from_message_id", None),
        "forward_preview": None,
        "is_encrypted": False,
        "encrypted_for_device": None,
    }


def broadcast_group_text_message(*, message, dialogue_slug: str, plain_text: str):
    """
    Broadcast one REST-created group text message to the dialogue realtime group.
    """
    payload = build_group_text_message_payload(
        message=message,
        dialogue_slug=dialogue_slug,
        plain_text=plain_text,
    )

    conv_group_send(
        conversation_dialogue_group_name(dialogue_slug),
        "chat_message",
        payload,
    )