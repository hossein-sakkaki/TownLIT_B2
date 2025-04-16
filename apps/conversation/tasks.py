# apps/conversation/tasks.py
from celery import shared_task
from django.db import transaction
from apps.conversation.models import Message, Dialogue
from django.contrib.auth import get_user_model
from services.redis_online_manager import get_all_online_users  # تابع جدید

User = get_user_model()

@shared_task
def deliver_offline_message(message_id):
    """
    Send a message that was queued when the user was offline.
    """
    try:
        message = Message.objects.get(id=message_id)
        recipient = message.dialogue.participants.exclude(id=message.sender.id).first()

        # ✅ بررسی آنلاین بودن کاربر از Redis
        online_users = asyncio.run(get_all_online_users())
        if recipient and recipient.id in online_users:
            # ✅ ارسال پیام به کاربر آنلاین
            from channels.layers import get_channel_layer
            import asyncio

            channel_layer = get_channel_layer()
            asyncio.run(channel_layer.group_send(
                f"user_{recipient.id}",
                {
                    "type": "chat_message",
                    "event_type": "chat_message",
                    "message_id": message.id,
                    "dialogue_id": message.dialogue.id,
                    "content": message.get_decrypted_content(),
                    "sender": {
                        "id": message.sender.id,
                        "username": message.sender.username,
                        "email": message.sender.email,
                    },
                    "timestamp": message.timestamp.isoformat(),
                    "is_encrypted": message.is_encrypted,
                    "is_delivered": True
                }
            ))

            # علامت‌گذاری پیام به عنوان تحویل داده‌شده
            message.is_delivered = True
            message.save(update_fields=["is_delivered"])

        else:
            # ❌ کاربر هنوز آنلاین نیست؛ پیام در صف باقی می‌ماند
            return "Recipient is still offline. Retry later."

    except Message.DoesNotExist:
        return f"❌ Message with ID {message_id} does not exist."

    return "✅ Message delivered successfully!"



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
