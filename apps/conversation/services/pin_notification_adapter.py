# apps/conversation/services/pin_notification_adapter.py

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def send_message_pin_reminder_notification(pin):
    """
    Dispatch one reminder notification through an isolated adapter.

    Notes:
    - Keep conversation domain decoupled from notifications domain.
    - Replace or extend this adapter to integrate with your stored
      notifications system service/viewset/contracts.
    """
    channel_layer = get_channel_layer()

    payload = {
        "type": "message_pin_reminder",
        "title": "Pinned message reminder",
        "body": f"You asked to be reminded about a pinned message in dialogue {pin.dialogue.slug}.",
        "dialogue_slug": pin.dialogue.slug,
        "message_id": pin.message_id,
        "pin_id": pin.id,
        "pin_duration": pin.pin_duration,
        "expires_at": pin.expires_at.isoformat() if pin.expires_at else None,
    }

    # Realtime app-level notification event
    async_to_sync(channel_layer.group_send)(
        f"user_{pin.pinned_by_id}",
        {
            "type": "dispatch_event",
            "app": "notifications",
            "event": "notification_created",
            "data": payload,
        },
    )