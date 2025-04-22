from channels.generic.websocket import AsyncJsonWebsocketConsumer
from asgiref.sync import sync_to_async
import json
import base64
from datetime import datetime
from apps.conversation.models import Message, Dialogue, MessageEncryption
from apps.accounts.models import UserDeviceKey
from django.contrib.auth import get_user_model
import asyncio
from django.utils import timezone
from django.utils.timesince import timesince
from .utils import get_message_content
from services.redis_online_manager import (
    set_user_online, set_user_offline, 
    get_all_online_users, get_online_status_for_users,
    refresh_user_connection, get_last_seen
)
from services.message_atomic_utils import (
    mark_message_as_delivered_atomic,
    mark_message_as_read_atomic,
    save_message_atomic
)
from apps.conversation.tasks import deliver_offline_message

import logging
logger = logging.getLogger(__name__)

User = get_user_model()

TYPING_TIMEOUTS = {}
DISCONNECT_TIMERS = {}



# Dialogue Consumer Class -------------------------------------------------------------------------
class DialogueConsumer(AsyncJsonWebsocketConsumer):  
    # Connect ---------------------------
    async def connect(self):
        self.connected = True
        self.user = self.scope["user"]

        # 🔐 استخراج device_id از query string
        query_string = self.scope.get("query_string", b"").decode()
        query_params = dict(qc.split("=") for qc in query_string.split("&") if "=" in qc)
        self.device_id = query_params.get("device_id")

        if not self.user or not self.user.is_authenticated or not self.device_id:
            await self.close()
            return

        # ✅ لغو تایمر قطع اتصال قبلی (در صورت reconnect)
        if DISCONNECT_TIMERS.get(self.user.id):
            DISCONNECT_TIMERS[self.user.id].cancel()
            del DISCONNECT_TIMERS[self.user.id]

        # ✅ ثبت آنلاین بودن کاربر
        await set_user_online(self.user.id, self.channel_name)

        # ✅ ثبت در گروه کاربر
        await self.channel_layer.group_add(f"user_{self.user.id}", self.channel_name)

        # ✅ ثبت در گروه دستگاه کاربر
        await self.channel_layer.group_add(f"device_{self.device_id}", self.channel_name)

        # ✅ ثبت در گروه‌های دیالوگ
        dialogues = await sync_to_async(list)(Dialogue.objects.filter(participants=self.user))
        self.group_names = set(f"dialogue_{dialogue.id}" for dialogue in dialogues)

        for group in self.group_names:
            await self.channel_layer.group_add(group, self.channel_name)

        await self.accept()

        asyncio.create_task(self.start_ping())
        await self.notify_user_online()
        await self.send_all_online_statuses()

        # ✅ ارسال وضعیت آنلاین به کاربر تازه متصل شده
        await self.send(text_data=json.dumps({
            "type": "user_online_status",
            "event_type": "user_online_status",
            "dialogue_ids": [dialogue.id for dialogue in dialogues],
            "user_id": self.user.id,
            "is_online": True
        }))

        # ✅ ارسال پیام‌های تحویل داده نشده
        for dialogue in dialogues:
            undelivered_messages = await sync_to_async(list)(
                dialogue.messages.filter(is_delivered=False).exclude(sender=self.user)
            )
            for message in undelivered_messages:
                await self.mark_message_as_delivered(message)

                content = get_message_content(message, self.user)


                await self.channel_layer.group_send(
                    f"dialogue_{dialogue.id}",
                    {
                        "type": "chat_message",
                        "event_type": "chat_message",
                        "message_id": message.id,
                        "dialogue_id": dialogue.id,
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
                await self.channel_layer.group_send(
                    f"user_{message.sender.id}",
                    {
                        "type": "mark_as_delivered",
                        "event_type": "mark_as_delivered",
                        "dialogue_id": dialogue.id,
                        "message_id": message.id,
                        "user_id": self.user.id,
                    }
                )

        for group in self.group_names:
            await self.channel_layer.group_send(
                group,
                {
                    "type": "user_online_status",
                    "event_type": "user_online_status",
                    "dialogue_id": int(group.split("_")[1]),
                    "user_id": self.user.id,
                    "is_online": True
                }
            )


    # User Online ---------------------------
    async def notify_user_online(self):
        # ✅ ارسال پیام‌های تحویل داده نشده برای این کاربر
        undelivered_messages = await sync_to_async(list)(
            Message.objects.filter(is_delivered=False, dialogue__participants=self.user)
        )
        for message in undelivered_messages:
            await self.mark_message_as_delivered(message)
            await self.notify_message_delivered_to_sender(message)

        for group in self.group_names:
            await self.channel_layer.group_send(
                group,
                {
                    "type": "user_online_status",
                    "event_type": "user_online_status",
                    "dialogue_id": int(group.split("_")[1]),
                    "user_id": self.user.id,
                    "is_online": True
                }
            )

            
    # Message Delivered after online ------------------------------
    async def notify_message_delivered_to_sender(self, message):
        recipient = await sync_to_async(
            lambda: message.dialogue.participants.exclude(id=message.sender.id).first()
        )()

        if not recipient:
            return

        await self.channel_layer.group_send(
            f"user_{message.sender.id}",  
            {
                "type": "mark_as_delivered",
                "dialogue_id": message.dialogue.id,
                "message_id": message.id,
                "user_id": recipient.id, 
            }
        )
            
    
    # User Offline ---------------------------       
    async def notify_user_offline(self):
        for group in self.group_names:
            await self.channel_layer.group_send(
                group,
                {
                    "type": "user_online_status",
                    "event_type": "user_online_status",
                    "dialogue_id": int(group.split("_")[1]),
                    "user_id": self.user.id,
                    "is_online": False
                }
            )

    # Online Status ---------------------------
    async def user_online_status(self, event):
        await self.send(text_data=json.dumps({
            "type": "user_online_status",
            "event_type": "user_online_status",
            "dialogue_id": event["dialogue_id"],
            "user_id": event["user_id"],
            "is_online": event["is_online"]
        }))
        
    # Send All Online Status ---------------------------
    async def send_all_online_statuses(self):
        online_users = await get_all_online_users()
        dialogues = await sync_to_async(list)(Dialogue.objects.filter(participants=self.user))
        for dialogue in dialogues:
            participants = await sync_to_async(list)(dialogue.participants.all())
            
            for participant in participants:
                is_online = participant.id in online_users
                await self.send(text_data=json.dumps({
                    "type": "user_online_status",
                    "event_type": "user_online_status",
                    "dialogue_id": dialogue.id,
                    "user_id": participant.id,
                    "is_online": is_online
                }))
                
    # Force Logout -------------------------------------------------
    async def force_logout(self, event):
        user_id = event["user_id"]

        if user_id == self.user.id:
            self.force_logout_triggered = True
            await self.finalize_disconnect()
            await self.close()

    # Disconnect ---------------------------------------------------
    async def disconnect(self, close_code):
        # ✅ بررسی خروج واقعی (اگر کاربر لاگ‌اوت کرده است)
        if getattr(self, "force_logout_triggered", False):
            await self.finalize_disconnect()
            return

        # ✅ لغو تایمر قطع اتصال اگر از قبل وجود دارد
        if DISCONNECT_TIMERS.get(self.user.id):
            DISCONNECT_TIMERS[self.user.id].cancel()
            del DISCONNECT_TIMERS[self.user.id]

        # ✅ تابع داخلی برای تأخیر در قطع اتصال
        async def delayed_disconnect():
            await asyncio.sleep(10)
            if not getattr(self, "connected", False):
                await self.finalize_disconnect()

        DISCONNECT_TIMERS[self.user.id] = asyncio.create_task(delayed_disconnect())

    # Finalize Disconnect -----------------------------------------
    async def finalize_disconnect(self):
        # 🔴 اعلام قطع اتصال
        self.connected = False

        # 🔴 توقف حلقه پینگ اگر در حال اجرا باشد
        if hasattr(self, "ping_task"):
            self.ping_task.cancel()
            try:
                await self.ping_task
            except asyncio.CancelledError:
                pass

        # حذف کاربر از Redis (لیست آنلاین‌ها)
        await set_user_offline(self.user.id, self.channel_name)

        # خروج از همه‌ی گروه‌ها
        for group in self.group_names:
            await self.channel_layer.group_discard(group, self.channel_name)

        await self.channel_layer.group_discard(f"user_{self.user.id}", self.channel_name)

        # ارسال پیام آفلاین شدن به همه‌ی گروه‌ها
        for group in self.group_names:
            await self.channel_layer.group_send(
                group,
                {
                    "type": "user_online_status",
                    "event_type": "user_online_status",
                    "dialogue_id": int(group.split("_")[1]),
                    "user_id": self.user.id,
                    "is_online": False
                }
            )

        # حذف تایمر تایپ (اگر وجود دارد)
        if TYPING_TIMEOUTS.get(self.user.id):
            TYPING_TIMEOUTS[self.user.id].cancel()
            del TYPING_TIMEOUTS[self.user.id]

        # حذف تایمر قطع اتصال (اگر وجود دارد)
        if DISCONNECT_TIMERS.get(self.user.id):
            del DISCONNECT_TIMERS[self.user.id]

        # ارسال وضعیت آخرین بازدید (last_seen)
        last_seen_ts = await get_last_seen(self.user.id)
        if last_seen_ts:
            last_seen_dt = datetime.fromtimestamp(last_seen_ts)
            last_seen_display = timesince(last_seen_dt) + " ago"

            for group in self.group_names:
                await self.channel_layer.group_send(
                    group,
                    {
                        "type": "user_last_seen",
                        "dialogue_id": int(group.split("_")[1]),
                        "user_id": self.user.id,
                        "last_seen": last_seen_dt.isoformat(),
                        "last_seen_display": last_seen_display
                    }
                )

        
    # Start Ping ---------------------------
    async def start_ping(self):
        try:
            while self.connected:
                online_statuses = await get_online_status_for_users([self.user.id])
                if online_statuses.get(self.user.id, False):
                    await self.send(text_data=json.dumps({
                        "type": "ping",
                        "timestamp": datetime.now().isoformat()
                    }))
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            # ✅ وظیفه‌ی پینگ کنسل شده
            pass
        except Exception as e:
            logger.error(f"[start_ping] Unexpected error: {e}")


    # Receive ---------------------------
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
                    
            if data.get("type") == "pong":
                await refresh_user_connection(self.user.id, self.channel_name)
                return 
            
            if data.get("type") == "upload_canceled":
                await self.handle_upload_canceled(data)
                return    
            
            if data.get("type") == "edit_message":
                await self.handle_edit_message(data)
                return      

            # Manage Typing
            if 'is_typing' in data:
                await self.handle_typing_status(data)
                return
            
            if data.get("type") == "chat_message":
                await self.handle_message(data)
                return            
            
            # File Manage
            if data.get("type") == "file_message":
                await self.handle_file_message(data)
                return
            
            if data.get("type") == "file_upload_status":
                await self.handle_file_upload_status(data)
                return

            if data.get("type") == "recording_status":
                await self.handle_recording_status(data)
                return
            
            if data.get("type") == "soft_delete_message":
                await self.handle_soft_delete_message(data)
                return

            if data.get("type") == "hard_delete_message":
                await self.handle_hard_delete_message(data)
                return
                    
            if data.get("type") == "mark_as_read":
                await self.mark_message_as_read(data)
                return

            if data.get("type") == "request_online_status":
                dialogue_id = data.get("dialogue_id")
                if not dialogue_id:
                    return

                dialogue = await sync_to_async(Dialogue.objects.get)(id=dialogue_id)
                participants = await sync_to_async(list)(dialogue.participants.all())
                participant_ids = [participant.id for participant in participants]
                online_statuses = await get_online_status_for_users(participant_ids)

                for participant in participants:
                    online_status = online_statuses.get(participant.id, False)
                    await self.send(text_data=json.dumps({
                        "type": "user_online_status",
                        "event_type": "user_online_status",
                        "dialogue_id": dialogue_id,
                        "user_id": participant.id,
                        "is_online": online_status
                    }))
                    
        except Exception as e:
            await self.send_json({"type": "error", "message": str(e)})

            
    # Typing Status ----------------------
    async def handle_typing_status(self, data):
        dialogue_id = data.get("dialogue_id")
        is_typing = data.get("is_typing", False)

        if not dialogue_id:
            return

        await self.channel_layer.group_send(
            f"dialogue_{dialogue_id}",
            {
                "type": "typing_status",
                "event_type": "typing_status",
                "dialogue_id": dialogue_id,
                "sender": {
                    "id": self.user.id,
                    "username": self.user.username,
                    "email": self.user.email
                },
                "is_typing": is_typing
            }
        )

        if is_typing:
            if TYPING_TIMEOUTS.get(self.user.id):
                TYPING_TIMEOUTS[self.user.id].cancel()
            TYPING_TIMEOUTS[self.user.id] = asyncio.create_task(self.clear_typing_status(dialogue_id))

    # Delete Typing Status after 5 sec ----------------------
    async def clear_typing_status(self, dialogue_id):
        await asyncio.sleep(5)
        await self.channel_layer.group_send(
            f"dialogue_{dialogue_id}",
            {
                "type": "typing_status",
                "event_type": "typing_status",
                "dialogue_id": dialogue_id,
                "sender": {
                    "id": self.user.id,
                    "username": self.user.username,
                    "email": self.user.email
                },
                "is_typing": False 
            }
        )
        if TYPING_TIMEOUTS.get(self.user.id):
            del TYPING_TIMEOUTS[self.user.id]

    
    # Handle Message ----------------------                
    async def handle_message(self, data):
        dialogue_id = data.get("dialogue_id")
        encrypted_contents = data.get("encrypted_contents", [])
        is_encrypted = data.get("is_encrypted", False)

        if not encrypted_contents or not isinstance(encrypted_contents, list):
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": "Missing or invalid encrypted contents."
            }))
            return

        try:
            dialogue = await sync_to_async(Dialogue.objects.get)(id=dialogue_id)
            if is_encrypted:
                message = await sync_to_async(Message.objects.create)(
                    dialogue=dialogue,
                    sender=self.user,
                    content_encrypted=b"[Encrypted]",
                    is_encrypted=True
                )
            else:
                plain_message = encrypted_contents[0].get("encrypted_content", "").strip()
                base64_str = base64.b64encode(plain_message.encode("utf-8")).decode("utf-8")
                content_bytes = base64_str.encode("utf-8")
                
                plain_message = encrypted_contents[0].get("encrypted_content", "")
                message = await sync_to_async(Message.objects.create)(
                    dialogue=dialogue,
                    sender=self.user,
                    content_encrypted=content_bytes,
                    is_encrypted=False
                )

            # 🧩 ذخیره نسخه‌های رمزنگاری‌شده (در پیام خصوصی)
            if is_encrypted:
                for item in encrypted_contents:
                    device_id = item.get("device_id")
                    encrypted_content = item.get("encrypted_content")
                    if not device_id or not encrypted_content:
                        continue

                    await sync_to_async(MessageEncryption.objects.create)(
                        message=message,
                        device_id=device_id,
                        encrypted_content=encrypted_content
                    )

            # 📌 بروزرسانی آخرین پیام گفتگو
            dialogue.last_message = message
            await sync_to_async(dialogue.save)(update_fields=['last_message'])

        except Exception as e:
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": "Failed to save message.",
                "details": str(e)
            }))
            return

        await self.handle_self_destruct_messages()

        # 🔍 همه شرکت‌کننده‌ها
        participants = await sync_to_async(list)(dialogue.participants.all())
        user_ids = [p.id for p in participants if p.id != self.user.id]
        online_statuses = await get_online_status_for_users(user_ids)

        for participant in participants:
            is_delivered = online_statuses.get(participant.id, False)

            # 🔐 ارسال پیام برای همه device ها
            if is_encrypted:
                # → خصوصی: بر اساس کلید دستگاه
                user_device_keys = await sync_to_async(list)(
                    UserDeviceKey.objects.filter(user=participant, is_active=True)
                )
                device_ids = [dk.device_id for dk in user_device_keys]

                for device_id in device_ids:
                    enc_obj = await sync_to_async(MessageEncryption.objects.filter)(
                        message=message,
                        device_id=device_id
                    )
                    if await sync_to_async(enc_obj.exists)():
                        enc = await sync_to_async(enc_obj.first)()
                        await self.channel_layer.group_send(
                            f"device_{device_id}",
                            {
                                "type": "chat_message",
                                "event_type": "chat_message",
                                "message_id": message.id,
                                "dialogue_id": dialogue_id,
                                "content": enc.encrypted_content,
                                "sender": {
                                    "id": self.user.id,
                                    "username": self.user.username,
                                    "email": self.user.email,
                                },
                                "timestamp": message.timestamp.isoformat(),
                                "is_encrypted": True,
                                "encrypted_for_device": device_id,
                                "is_delivered": is_delivered
                            }
                        )
            else:
                # → گروهی: ارسال پیام برای هر کاربر (فقط یک نسخه برای همه)
                await self.channel_layer.group_send(
                    f"user_{participant.id}",
                    {
                        "type": "chat_message",
                        "event_type": "chat_message",
                        "message_id": message.id,
                        "dialogue_id": dialogue_id,
                        "content": plain_message,
                        "sender": {
                            "id": self.user.id,
                            "username": self.user.username,
                            "email": self.user.email,
                        },
                        "timestamp": message.timestamp.isoformat(),
                        "is_encrypted": False,
                        "encrypted_for_device": None,
                        "is_delivered": is_delivered
                    }
                )

            if is_delivered:
                await self.mark_message_as_delivered(message)
            else:
                deliver_offline_message.delay(message.id)

            await self.channel_layer.group_send(
                f"user_{participant.id}",
                {
                    "type": "trigger_unread_count_update"
                }
            )



    # Save Message ----------------------
    @sync_to_async
    def save_message(self, dialogue_id, content, is_encrypted):
        dialogue = Dialogue.objects.get(id=dialogue_id)   
            
        if dialogue.deleted_by_users.filter(id=self.user.id).exists():
            dialogue.deleted_by_users.remove(self.user) 
            
        content_to_store = content.encode()
        message = Message.objects.create(
            dialogue=dialogue,
            sender=self.user,
            content_encrypted=content_to_store
        )
        
        dialogue.last_message = message
        dialogue.save(update_fields=['last_message'])
        
        return message

    async def handle_self_destruct_messages(self):
        messages_to_delete = await sync_to_async(Message.objects.filter)(
            sender=self.user,
            self_destruct_at__lte=datetime.now()
        )
        await sync_to_async(messages_to_delete.delete)()

    async def chat_message(self, event):
        event["type"] = "chat_message"
        await self.send(text_data=json.dumps(event))
        
    async def typing_status(self, event):
        await self.send(text_data=json.dumps({
            "type": "typing_status",
            "event_type": "typing_status",
            "dialogue_id": event["dialogue_id"],
            "sender": event["sender"],
            "is_typing": event["is_typing"]
        }))
    
    
    # Mark as Delieverd Message and send to Partner User ------------------------------------------
    async def mark_message_as_delivered(self, message):
        recipient = await sync_to_async(
            lambda: message.dialogue.participants.exclude(id=message.sender.id).first()
        )()

        if not recipient:
            return

        online_statuses = await get_online_status_for_users([recipient.id])
        recipient_online = online_statuses.get(recipient.id, False)

        if recipient_online:
            await mark_message_as_delivered_atomic(message)

            await self.send(text_data=json.dumps({
                "type": "mark_as_delivered",
                "dialogue_id": message.dialogue.id,
                "message_id": message.id,
                "is_delivered": True
            }))

            await self.channel_layer.group_send(
                f"user_{message.sender.id}",
                {
                    "type": "mark_as_delivered",
                    "dialogue_id": message.dialogue.id,
                    "message_id": message.id,
                    "user_id": self.user.id,  # یا recipient.id
                }
            )


    # Mark as Delivered Message and send to Sender User --------------------------------------------
    async def mark_as_delivered(self, event):
        await self.send(text_data=json.dumps({
            "type": "mark_as_delivered",
            "dialogue_id": event["dialogue_id"],
            "message_id": event["message_id"],
            "user_id": event["user_id"],
        }))

         
    # Mark as Read Real-Time Update ----------------------------------------------------------------
    async def mark_message_as_read(self, data):
        dialogue_id = data.get("dialogue_id")
        if not dialogue_id:
            return

        dialogue = await sync_to_async(Dialogue.objects.get)(id=dialogue_id)
        unread_messages = await sync_to_async(list)(
            Message.objects.filter(dialogue=dialogue).exclude(seen_by_users=self.user)
        )
                
        for message in unread_messages:
            if message.sender_id == self.user.id:
                continue 
            await mark_message_as_read_atomic(message, self.user)


            await self.channel_layer.group_send(
                f"dialogue_{dialogue_id}",
                {
                    "type": "mark_as_read",
                    "event_type": "mark_as_read",
                    "dialogue_id": dialogue_id,
                    "reader": {
                        "id": self.user.id,
                        "username": self.user.username,
                        "email": self.user.email,
                    },
                    "read_messages": [msg.id for msg in unread_messages]
                }
            )
            await self.send_unread_counts()

    # Mark as Read  ----------------------
    async def mark_as_read(self, event):
        await self.send(text_data=json.dumps(event))

    # Handle File Messages ----------------------
    async def handle_file_message(self, data):
        dialogue_id = data.get("dialogue_id")
        message_id = data.get("message_id")  
        file_type = data.get("file_type")
        file_url = data.get("file_url")

        if not dialogue_id or not message_id or not file_type or not file_url:
            return

        try:
            message = await sync_to_async(Message.objects.get)(id=message_id, dialogue_id=dialogue_id)
        except Message.DoesNotExist:
            return

        sender = await sync_to_async(lambda: {
            "id": message.sender.id,
            "username": message.sender.username,
            "email": message.sender.email,
        })()

        # ✅ دریافت لیست کاربران (بجز فرستنده)
        participants = await sync_to_async(
            lambda: list(message.dialogue.participants.exclude(id=message.sender.id).values_list("id", flat=True))
        )()

        for user_id in participants:
            await self.channel_layer.group_send(
                f"user_{user_id}",
                {
                    "type": "file_message",
                    "event_type": "file_message",
                    "message_id": message.id,
                    "dialogue_id": dialogue_id,
                    "file_type": file_type,
                    "file_url": file_url,
                    "sender": sender,
                    "timestamp": message.timestamp.isoformat(),
                    "is_encrypted_file": message.is_encrypted_file,
                    "is_encrypted": message.is_encrypted,
                }
            )

    # Handle File Canceled Message ----------------------
    async def handle_upload_canceled(self, data):
        dialogue_id = data.get("dialogue_id")
        file_type = data.get("file_type")

        if not dialogue_id or not file_type:
            return
        
        # ✅ ارسال پیام به سایر کاربران این دیالوگ که آپلود لغو شده است
        await self.channel_layer.group_send(
            f"dialogue_{dialogue_id}",
            {
                "type": "file_upload_status",
                "event_type": "file_upload_status",
                "dialogue_id": dialogue_id,
                "file_type": file_type,
                "status": "cancelled",
                "progress": 0,
            }
        )

        # ✅ ارسال تأییدیه لغو آپلود به فرستنده
        await self.send(text_data=json.dumps({
            "type": "upload_canceled",
            "dialogue_id": dialogue_id,
            "file_type": file_type,
            "status": "cancelled"
        }))



    # File Message Event to User ----------------------
    async def file_message(self, event):
        await self.send(text_data=json.dumps(event))
        
            
    # ارسال وضعیت ارسال فایل (در حال آپلود، در حال پردازش، آماده ارسال) ----------------------------------------------
    async def send_file_status(self, dialogue_id, file_type, status, progress=None):
        await self.channel_layer.group_send(
            f"dialogue_{dialogue_id}",
            {
                "type": "file_upload_status",
                "event_type": "file_upload_status",
                "dialogue_id": dialogue_id,
                "sender": {
                    "id": self.user.id,
                    "username": self.user.username,
                    "email": self.user.email,
                },
                "file_type": file_type,
                "status": status,  # pending, uploading, processing, completed
                "progress": progress,
            }
        )
        
    async def handle_file_upload_status(self, data):
        dialogue_id = data.get("dialogue_id")
        file_type = data.get("file_type")
        status = data.get("status")
        progress = data.get("progress", None)

        if not dialogue_id or not file_type or not status:
            return

        await self.send_file_status(dialogue_id, file_type, status, progress)
        
    async def handle_recording_status(self, data):
        dialogue_id = data.get("dialogue_id")
        is_recording = data.get("is_recording", False)
        file_type = data.get("file_type")  # "audio" یا "video"

        if not dialogue_id or not file_type:
            return

        await self.channel_layer.group_send(
            f"dialogue_{dialogue_id}",
            {
                "type": "recording_status",
                "event_type": "recording_status",
                "dialogue_id": dialogue_id,
                "sender": {
                    "id": self.user.id,
                    "username": self.user.username,
                    "email": self.user.email,
                },
                "is_recording": is_recording,
                "file_type": file_type,
            }
        )

    async def file_upload_status(self, event):
        await self.send(text_data=json.dumps(event))

    async def recording_status(self, event):
        await self.send(text_data=json.dumps(event))
            

    # Handle Edit Message ------------------------------------------------------
    async def handle_edit_message(self, data):
        message_id = data.get("message_id")
        encrypted_contents = data.get("encrypted_contents", [])
        is_encrypted = data.get("is_encrypted", False)

        if not message_id:
            return

        try:
            message = await sync_to_async(Message.objects.select_related("dialogue").get)(id=message_id)
        except Message.DoesNotExist:
            return

        if await sync_to_async(lambda: message.sender.id)() != self.user.id:
            return

        dialogue = await sync_to_async(lambda: message.dialogue)()
        now = timezone.now()

        if is_encrypted:
            # حذف نسخه‌های قبلی رمزنگاری‌شده
            await sync_to_async(MessageEncryption.objects.filter(message=message).delete)()

            # ثبت پیام به‌روزرسانی‌شده
            await sync_to_async(setattr)(message, "content_encrypted", b"[Encrypted]")
            await sync_to_async(setattr)(message, "is_edited", True)
            await sync_to_async(setattr)(message, "edited_at", now)
            await sync_to_async(setattr)(message, "is_encrypted", True)
            await sync_to_async(message.save)()

            # ذخیره نسخه‌های جدید رمزنگاری‌شده
            for item in encrypted_contents:
                device_id = item.get("device_id")
                encrypted_content = item.get("encrypted_content")
                if not device_id or not encrypted_content:
                    continue
                await sync_to_async(MessageEncryption.objects.create)(
                    message=message,
                    device_id=device_id,
                    encrypted_content=encrypted_content
                )

        else:            
            new_content = data.get("new_content", "").strip()
            if not new_content:
                return

            base64_str = base64.b64encode(new_content.encode("utf-8")).decode("utf-8")
            content_bytes = base64_str.encode("utf-8")
            await sync_to_async(setattr)(message, "content_encrypted", content_bytes)

            await sync_to_async(setattr)(message, "is_edited", True)
            await sync_to_async(setattr)(message, "edited_at", now)
            await sync_to_async(setattr)(message, "is_encrypted", False)
            await sync_to_async(message.save)()

        # بروزرسانی آخرین پیام گفتگو (اختیاری)
        dialogue.last_message = message
        await sync_to_async(dialogue.save)(update_fields=["last_message"])

        # آماده‌سازی ارسال به کاربران (WebSocket)
        participants = await sync_to_async(list)(dialogue.participants.all())

        for participant in participants:
            
            if is_encrypted:
                # فقط اگر کلید برای participant داریم
                user_device_keys = await sync_to_async(list)(
                    UserDeviceKey.objects.filter(user=participant, is_active=True)
                )

                for device_key in user_device_keys:
                    enc = await sync_to_async(MessageEncryption.objects.filter(
                        message=message,
                        device_id=device_key.device_id
                    ).first)()

                    if not enc:
                        continue


                    await self.channel_layer.group_send(
                        f"device_{device_key.device_id}",
                        {
                            "type": "edit_message",
                            "message_id": message.id,
                            "dialogue_id": dialogue.id,
                            "edited_at": now.isoformat(),
                            "is_encrypted": True,
                            "is_edited": True,
                            "encrypted_contents": [{
                                "device_id": device_key.device_id,
                                "encrypted_content": enc.encrypted_content
                            }],
                            "sender": {
                                "id": message.sender.id,
                                "username": message.sender.username,
                            },
                        }
                    )
                    
            else:
                await self.channel_layer.group_send(
                    f"user_{participant.id}",
                    {
                        "type": "edit_message",
                        "message_id": message.id,
                        "dialogue_id": dialogue.id,
                        "new_content": data.get("new_content", ""),
                        "edited_at": now.isoformat(),
                        "is_encrypted": False,
                        "is_edited": True,
                        "sender": {
                            "id": message.sender.id,
                            "username": message.sender.username,
                        },
                        "decrypted_content": data.get("new_content", ""),
                    }
                )



    # Handle Real-Time Edit Update ----------------------------------------------
    async def edit_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "edit_message",
            "message_id": event["message_id"],
            "dialogue_id": event["dialogue_id"],
            "edited_at": event["edited_at"],
            "is_encrypted": event.get("is_encrypted", False),
            "is_edited": event.get("is_edited", True),
            "new_content": event.get("new_content"),  # فقط برای پیام‌های گروهی
            "encrypted_contents": event.get("encrypted_contents"),  # فقط برای خصوصی
        }))

        
    # Soft Delete Message Handler ------------------------------------------------
    async def handle_soft_delete_message(self, data):
        message_id = data.get("message_id")
        user = self.user

        try:
            message = await sync_to_async(Message.objects.select_related("dialogue").get)(id=message_id)
        except Message.DoesNotExist:
            return

        await sync_to_async(lambda: message.mark_as_deleted_by_user(user))()

        # dialogue_id = await sync_to_async(lambda: message.dialogue.id)()

        # await self.channel_layer.group_send(
        #     f"dialogue_{dialogue_id}",
        #     {
        #         "type": "message_soft_deleted",
        #         "message_id": message.id,
        #         "user_id": user.id,
        #     }
        # )
        await self.send(text_data=json.dumps({
            "type": "message_soft_deleted",
            "message_id": message.id,
            "user_id": user.id,
        }))
        
        await self.channel_layer.group_send(
            f"user_{user.id}",
            {
                "type": "trigger_unread_count_update"
            }
        )


    async def message_soft_deleted(self, event):
        await self.send(text_data=json.dumps({
            "type": "message_soft_deleted",
            "message_id": event["message_id"],
            "user_id": event["user_id"],
        }))

    # Hard Delete Message Handler ------------------------------------------------
    async def handle_hard_delete_message(self, data):
        message_id = data.get("message_id")
        user = self.user

        try:
            message = await sync_to_async(Message.objects.select_related("dialogue").get)(id=message_id)
        except Message.DoesNotExist:
            return

        dialogue = await sync_to_async(lambda: message.dialogue)()
        is_sender = await sync_to_async(lambda: message.sender.id == user.id)()
        is_unseen = await sync_to_async(lambda: message.seen_by_users.count() == 0)()
        is_group_admin = await sync_to_async(lambda: dialogue.is_group and dialogue.is_admin(user))()

        if (is_sender and is_unseen) or is_group_admin:
            if message.image:
                await sync_to_async(message.image.delete)(save=False)
            if message.video:
                await sync_to_async(message.video.delete)(save=False)
            if message.audio:
                await sync_to_async(message.audio.delete)(save=False)
            if message.file:
                await sync_to_async(message.file.delete)(save=False)

            # 🔐 حذف رمزنگاری‌های مرتبط
            await sync_to_async(lambda: message.encryptions.all().delete())()

            dialogue_id = dialogue.id
            await sync_to_async(message.delete)()

            # ✅ به همه کاربران گفتگو
            await self.channel_layer.group_send(
                f"dialogue_{dialogue_id}",
                {
                    "type": "message_hard_deleted",
                    "dialogue_id": dialogue_id,
                    "message_id": message_id,
                }
            )

            # ✅ به فرستنده (مستقیم)
            await self.send(text_data=json.dumps({
                "type": "message_hard_deleted",
                "dialogue_id": dialogue_id,
                "message_id": message_id,
            }))

            # ✅ بروزرسانی شمارنده برای همه‌ی کاربران دیالوگ (به‌جز فرستنده)
            participants = await sync_to_async(list)(dialogue.participants.exclude(id=user.id))
            for participant in participants:
                await self.channel_layer.group_send(
                    f"user_{participant.id}",
                    {
                        "type": "trigger_unread_count_update"
                    }
                )

            # ✅ (اختیاری) حتی برای فرستنده هم دوباره بفرستیم
            await self.channel_layer.group_send(
                f"user_{user.id}",
                {
                    "type": "trigger_unread_count_update"
                }
            )

        
    async def message_hard_deleted(self, event):
        await self.send(text_data=json.dumps({
            "type": "message_hard_deleted",
            "dialogue_id": event["dialogue_id"],
            "message_id": event["message_id"],
        }))

    # Last Seen -----------------------------------------------------------------
    async def user_last_seen(self, event):
        await self.send(text_data=json.dumps({
            "type": "user_last_seen",
            "dialogue_id": event["dialogue_id"],
            "user_id": event["user_id"],
            "last_seen": event["last_seen"],
            "last_seen_display": event["last_seen_display"],
        }))


    # Group Added ---------------------------------------------------------------
    async def group_added(self, event):        
        await self.send_json({
            "type": "group_added",
            "dialogue": event["dialogue"]
        })

    # Group Removed -------------------------------------------------------------
    async def group_removed(self, event):
        await self.send_json({
            "type": "group_removed",
            "dialogue": event["dialogue"]
        })
        
    # Group Left ----------------------------------------------------------------
    async def group_left(self, event):
        await self.send_json({
            "type": "group_left",
            "user": event["user"],
            "dialogue_id": event["dialogue_id"],
        })
        
    # Founder Transferred -------------------------------------------------------
    async def founder_transferred(self, event):
        await self.send_json({
            "type": "founder_transferred",
            "dialogue_id": event["dialogue_id"],
            "new_founder_id": event["new_founder_id"],
        })
        

    # Send Unread Counts ------------------------------------------------------
    async def send_unread_counts(self):
        user = self.user
        dialogues = await sync_to_async(list)(
            Dialogue.objects.filter(participants=user)
        )

        results = []
        for dialogue in dialogues:
            unread_count = await sync_to_async(
                lambda: dialogue.messages
                    .exclude(seen_by_users=user)
                    .exclude(sender=user)
                    .count()
            )()
            
            results.append({
                "dialogue_id": dialogue.id,
                "unread_count": unread_count
            })

        await self.send_json({
            "type": "unread_count_update",
            "payload": results
        })


    async def trigger_unread_count_update(self, event):
        await self.send_unread_counts()