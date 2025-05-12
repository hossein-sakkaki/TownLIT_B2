from celery import shared_task
from django.db import transaction
from django.contrib.auth import get_user_model
from services.redis_online_manager import get_all_online_users
from apps.conversation.models import Message, Dialogue
from channels.layers import get_channel_layer
import asyncio
from django.utils.timezone import now
from datetime import timedelta
from services.redis_online_manager import get_all_online_users
import asyncio
from asgiref.sync import async_to_sync

User = get_user_model()

@shared_task
def deliver_offline_message(message_id):
    """
    Deliver a queued message if the recipient is online.
    """
    try:
        message = Message.objects.select_related('dialogue', 'sender').get(id=message_id)
        recipient = message.dialogue.participants.exclude(id=message.sender.id).first()

        if not recipient:
            return f"❌ No valid recipient found for message {message_id}"

        # ✅ Get list of currently online users (from Redis)
        online_users = async_to_sync(get_all_online_users)()
        if recipient.id not in online_users:
            return f"ℹ️ Recipient {recipient.id} is still offline."

        # ✅ Send message via WebSocket
        channel_layer = get_channel_layer()
        content = message.get_decrypted_content() if message.is_encrypted else message.content_encrypted.decode()

        async_to_sync(channel_layer.group_send)(
            f"user_{recipient.id}",
            {
                "type": "chat_message",
                "event_type": "chat_message",
                "message_id": message.id,
                "dialogue_id": message.dialogue.id,
                "content": content,
                "sender": {
                    "id": message.sender.id,
                    "username": message.sender.username,
                    "email": message.sender.email,
                },
                "timestamp": message.timestamp.isoformat(),
                "is_encrypted": message.is_encrypted,
                "is_delivered": True
            }
        )

        # ✅ Mark message as delivered
        message.is_delivered = True
        message.save(update_fields=["is_delivered"])

        return f"✅ Message {message_id} delivered to user {recipient.id}"

    except Message.DoesNotExist:
        return f"❌ Message with ID {message_id} does not exist."
    



@shared_task
def retry_undelivered_messages():
    """
    Retry delivery of undelivered messages to users who are now online.
    """
    messages = Message.objects.filter(
        is_delivered=False,
        timestamp__lte=now() - timedelta(minutes=1)  # پیام‌های قدیمی‌تر از 1 دقیقه
    ).select_related("dialogue", "sender")

    online_user_ids = async_to_sync(get_all_online_users)()
    retry_count = 0

    for message in messages:
        recipient = message.dialogue.participants.exclude(id=message.sender.id).first()
        if recipient and recipient.id in online_user_ids:
            from .tasks import deliver_offline_message
            deliver_offline_message.delay(message.id)
            retry_count += 1

    return f"✅ Retried delivery for {retry_count} messages."




# @shared_task
# def mark_message_as_read_task(user_id, dialogue_id):
#     try:
#         user = User.objects.get(id=user_id)
#         dialogue = Dialogue.objects.get(id=dialogue_id)

#         # ✅ بروزرسانی پیام‌های خوانده‌نشده
#         unread_messages = Message.objects.filter(dialogue=dialogue).exclude(seen_by_users=user)

#         # ✅ جلوگیری از حلقه: فقط پیام‌های خوانده‌نشده را به‌روزرسانی کن
#         if unread_messages.exists():
#             for message in unread_messages:
#                 message.seen_by_users.add(user)
#                 message.save()

#     except User.DoesNotExist:
#         print(f"❌ User with ID {user_id} does not exist.")
#     except Dialogue.DoesNotExist:
#         print(f"❌ Dialogue with ID {dialogue_id} does not exist.")
