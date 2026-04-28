# apps/core/websocket/services/presence_broadcast.py
# =========================================================
#               Presence Broadcast Services
# =========================================================

from __future__ import annotations

from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer

from apps.conversation.models import Dialogue


async def get_presence_recipient_user_ids(user_id: int) -> list[int]:
    """
    Return users who are allowed to receive presence updates for this user.

    Current rule:
    - all users who share at least one dialogue with this user
    - includes self for self-sync consistency
    """
    dialogue_ids = await sync_to_async(list)(
        Dialogue.objects.filter(participants__id=user_id)
        .values_list("id", flat=True)
        .distinct()
    )

    if not dialogue_ids:
        return [int(user_id)]

    participant_ids = await sync_to_async(list)(
        Dialogue.objects.filter(id__in=dialogue_ids)
        .values_list("participants__id", flat=True)
        .distinct()
    )

    result = {int(uid) for uid in participant_ids if uid}
    result.add(int(user_id))
    return sorted(result)


async def broadcast_presence_event(
    *,
    user_id: int,
    event_name: str,
    data: dict,
) -> None:
    """
    Broadcast one canonical presence event to all eligible recipients.
    """
    channel_layer = get_channel_layer()
    recipient_ids = await get_presence_recipient_user_ids(user_id)

    for recipient_id in recipient_ids:
        await channel_layer.group_send(
            f"user_{recipient_id}",
            {
                "type": "dispatch_event",
                "app": "presence",
                "event": event_name,
                "data": data,
            },
        )


async def broadcast_user_online_status(user_id: int, is_online: bool) -> None:
    """
    Broadcast online/offline status.
    """
    await broadcast_presence_event(
        user_id=user_id,
        event_name="user_online_status",
        data={
            "user_id": int(user_id),
            "is_online": bool(is_online),
        },
    )


async def broadcast_user_last_seen(user_id: int, payload: dict) -> None:
    """
    Broadcast last seen payload.
    """
    normalized = {
        "user_id": int(user_id),
        "is_online": False,
        "last_seen_epoch": payload.get("last_seen_epoch"),
        "last_seen": payload.get("last_seen"),
        "last_seen_display": payload.get("last_seen_display"),
    }

    await broadcast_presence_event(
        user_id=user_id,
        event_name="user_last_seen",
        data=normalized,
    )