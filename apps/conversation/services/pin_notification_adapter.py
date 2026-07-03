# apps/conversation/services/pin_notification_adapter.py

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.conversation.services.messenger_notification_adapter import (
    notify_message_pinned,
)


def send_message_pin_reminder_notification(pin):
    """
    Dispatch one reminder notification through an isolated adapter.

    This reminder is a user-requested reminder for the pinner only.
    It is intentionally different from group pin push alerts.
    """
    channel_layer = get_channel_layer()

    if not channel_layer:
        return

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

    # Realtime reminder for the pinner only.
    async_to_sync(channel_layer.group_send)(
        f"user_{pin.pinned_by_id}",
        {
            "type": "dispatch_event",
            "app": "notifications",
            "event": "notification_created",
            "data": payload,
        },
    )


def send_message_pinned_push_notification(*, pin, actor):
    """
    Push-only alert for group members when a message is pinned.
    """
    notify_message_pinned(
        pin=pin,
        actor=actor,
    )
    
    
    
    