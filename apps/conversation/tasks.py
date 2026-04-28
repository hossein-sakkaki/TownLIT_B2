# apps/conversation/tasks.py

from celery import shared_task
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from django.utils.timezone import now
from datetime import timedelta

from apps.conversation.models import Message, MessageEncryption
from apps.accounts.models.devices import UserDeviceKey
from apps.core.websocket.services.redis_online_manager import get_all_online_users
from apps.conversation.services.message_atomic_utils import mark_message_as_delivered_atomic
from apps.conversation.utils import get_message_content

from apps.conversation.services.message_pins import (
    expire_due_message_pins,
    collect_due_pin_reminders,
)
from apps.conversation.services.pin_notification_adapter import (
    send_message_pin_reminder_notification,
)


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def _build_sender_payload(user):
    """Build canonical sender payload."""
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
    }


def _get_dm_recipient(message):
    """Return the other participant in a private dialogue."""
    return message.dialogue.participants.exclude(id=message.sender_id).first()


def _get_active_device_ids_for_user(user_id: int) -> set[str]:
    """Return active device ids for one user."""
    return set(
        UserDeviceKey.objects.filter(user_id=user_id, is_active=True)
        .values_list("device_id", flat=True)
    )


def _send_to_group(group_name: str, event_name: str, data: dict):
    """Send one canonical realtime event."""
    if not group_name:
        return

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": "dispatch_event",
            "app": "conversation",
            "event": event_name,
            "data": data,
        },
    )


# -------------------------------------------------------------------
# Deliver one offline DM message when recipient is online
# -------------------------------------------------------------------
@shared_task
def deliver_offline_message(message_id: int):
    """
    Deliver one queued private message if the recipient is online.

    Notes:
    - This task is for private dialogue recovery only.
    - Group delivery is not handled here.
    - Realtime envelope is canonical: app/event/data.
    """
    try:
        message = (
            Message.objects.select_related("dialogue", "sender")
            .prefetch_related("encryptions")
            .get(id=message_id)
        )
    except Message.DoesNotExist:
        return f"Message {message_id} not found."

    dialogue = message.dialogue

    # Only private dialogue delivery belongs here
    if dialogue.is_group:
        return f"Message {message_id} belongs to a group dialogue. Skipped."

    recipient = _get_dm_recipient(message)
    if not recipient:
        return f"No valid recipient found for message {message_id}."

    online_user_ids = async_to_sync(get_all_online_users)()
    if recipient.id not in online_user_ids:
        return f"Recipient {recipient.id} is still offline."

    # Mark delivered first
    async_to_sync(mark_message_as_delivered_atomic)(message)

    sender_payload = _build_sender_payload(message.sender)

    # ---------------------------------------------------------------
    # Encrypted DM -> deliver per recipient device group
    # ---------------------------------------------------------------
    has_encryptions = message.encryptions.exists()

    if has_encryptions:
        recipient_device_ids = _get_active_device_ids_for_user(recipient.id)

        if not recipient_device_ids:
            return f"Recipient {recipient.id} has no active devices."

        enc_rows = list(
            MessageEncryption.objects.filter(message=message)
            .values("device_id", "encrypted_content")
        )

        delivered_to_any_device = False

        for enc in enc_rows:
            device_id = enc["device_id"]
            encrypted_blob = enc["encrypted_content"]

            if device_id not in recipient_device_ids:
                continue

            payload = {
                "message_id": message.id,
                "dialogue_slug": dialogue.slug,
                "content": encrypted_blob,
                "sender": sender_payload,
                "timestamp": message.timestamp.isoformat(),
                "is_encrypted": True,
                "encrypted_for_device": device_id,
                "is_delivered": True,
                "is_system": getattr(message, "is_system", False),
                "system_event": getattr(message, "system_event", None),
            }

            _send_to_group(
                f"user_device_{recipient.id}_{device_id}",
                "chat_message",
                payload,
            )
            delivered_to_any_device = True

        if not delivered_to_any_device:
            return (
                f"Recipient {recipient.id} is online, but no matching encrypted "
                f"device envelope was found for message {message_id}."
            )

    # ---------------------------------------------------------------
    # Plaintext fallback -> deliver to user group
    # ---------------------------------------------------------------
    else:
        plain_content = get_message_content(message, recipient)

        payload = {
            "message_id": message.id,
            "dialogue_slug": dialogue.slug,
            "content": None,
            "decrypted_content": plain_content,
            "sender": sender_payload,
            "timestamp": message.timestamp.isoformat(),
            "is_encrypted": False,
            "encrypted_for_device": None,
            "is_delivered": True,
            "is_system": getattr(message, "is_system", False),
            "system_event": getattr(message, "system_event", None),
        }

        _send_to_group(
            f"user_{recipient.id}",
            "chat_message",
            payload,
        )

    # ---------------------------------------------------------------
    # Notify sender that recipient received delivery
    # ---------------------------------------------------------------
    _send_to_group(
        f"user_{message.sender_id}",
        "mark_as_delivered",
        {
            "dialogue_slug": dialogue.slug,
            "message_id": message.id,
            "user_id": recipient.id,
            "is_delivered": True,
        },
    )

    return f"Message {message_id} delivered to recipient {recipient.id}."


# -------------------------------------------------------------------
# Retry undelivered private messages for users who are now online
# -------------------------------------------------------------------
@shared_task
def retry_undelivered_messages():
    """
    Retry private undelivered messages for recipients who are online now.

    Notes:
    - This task scans only private dialogues.
    - It defers actual delivery to deliver_offline_message().
    """
    messages = (
        Message.objects.select_related("dialogue", "sender")
        .filter(
            is_delivered=False,
            dialogue__is_group=False,
            timestamp__lte=now() - timedelta(minutes=1),
        )
        .order_by("timestamp")
    )

    online_user_ids = set(async_to_sync(get_all_online_users)())
    retry_count = 0

    for message in messages:
        recipient = _get_dm_recipient(message)
        if not recipient:
            continue

        if recipient.id not in online_user_ids:
            continue

        deliver_offline_message.delay(message.id)
        retry_count += 1

    return f"Retried delivery for {retry_count} private messages."


# -------------------------------------------------------------------
# Expire due message pins
# -------------------------------------------------------------------
@shared_task
def cleanup_expired_message_pins():
    """
    Remove expired message pins and keep pin order compact.
    """
    result = expire_due_message_pins()

    if not result.get("ok"):
        return "Failed to expire message pins."

    payload = result["payload"]
    return f"Expired {payload['expired_count']} message pins."


# -------------------------------------------------------------------
# Send due pin reminders
# -------------------------------------------------------------------
@shared_task
def send_due_message_pin_reminders():
    """
    Send reminder notifications for due message pins.
    """
    result = collect_due_pin_reminders()

    if not result.get("ok"):
        return "Failed to collect due pin reminders."

    pins = result["payload"]["pins"]

    for pin in pins:
        send_message_pin_reminder_notification(pin)

    return f"Sent {len(pins)} message pin reminders."