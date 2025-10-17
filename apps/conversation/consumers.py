from channels.generic.websocket import AsyncJsonWebsocketConsumer
from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from typing import Dict, Tuple
import asyncio
import json
import base64
import time
from contextlib import suppress
from urllib.parse import parse_qs
from datetime import datetime
from apps.conversation.models import Message, Dialogue, MessageEncryption
from apps.accounts.models import UserDeviceKey
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.timesince import timesince
from .utils import get_message_content
from services.redis_online_manager import (
    set_user_online, set_user_offline, 
    get_all_online_users, get_online_status_for_users,
    refresh_user_connection, get_last_seen, get_redis_connection
)
from apps.accounts.services.sender_verification import is_sender_device_verified
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
DISCONNECT_TIMERS: Dict[Tuple[int, str], asyncio.Task] = {}



# Dialogue Consumer Class -------------------------------------------------------------------------
class DialogueConsumer(AsyncJsonWebsocketConsumer):  
    # Connect ---------------------------
    async def connect(self):
        self.connected = True
        self.user = self.scope.get("user")
        self.slug = self.scope["url_route"]["kwargs"].get("slug")

        # --- Parse & normalize device_id from query string safely ---
        qs = parse_qs(self.scope.get("query_string", b"").decode())
        device_id = (qs.get("device_id", [""])[0] or "").strip().lower()
        self.device_id = device_id if device_id else None

        # Basic auth/device guard
        if not self.user or not self.user.is_authenticated or not self.device_id:
            await self.close()
            return

        # Ensure the device belongs to this user and is active
        belongs = await database_sync_to_async(
            UserDeviceKey.objects.filter(
                user=self.user, device_id=self.device_id, is_active=True
            ).exists
        )()
        if not belongs:
            await self.close(code=4403)  # Forbidden-like
            return

        # ✅ Cancel any pending disconnect timer for THIS exact connection
        key = self._disc_key()
        if DISCONNECT_TIMERS.get(key):
            DISCONNECT_TIMERS[key].cancel()
            del DISCONNECT_TIMERS[key]

        # ✅ Mark user online
        await set_user_online(self.user.id, self.channel_name)

        # ✅ Join user/device groups (use normalized device_id)
        await self.channel_layer.group_add(f"user_{self.user.id}", self.channel_name)
        await self.channel_layer.group_add(f"device_{self.device_id}", self.channel_name)

        # Load dialogues
        if self.slug:
            try:
                dialogue = await sync_to_async(Dialogue.objects.get)(slug=self.slug, participants=self.user)
                self.dialogue_map = {f"dialogue_{dialogue.slug}": dialogue.id}
                dialogues = [dialogue]
            except Dialogue.DoesNotExist:
                await self.close()
                return
        else:
            dialogues = await sync_to_async(list)(Dialogue.objects.filter(participants=self.user))
            self.dialogue_map = {f"dialogue_{d.slug}": d.id for d in dialogues}

        self.group_names = set(self.dialogue_map.keys())
        for group in self.group_names:
            await self.channel_layer.group_add(group, self.channel_name)

        await self.accept()

        # Create and keep a reference to ping task so we can cancel it on disconnect
        self.ping_task = asyncio.create_task(self.start_ping())

        # Notify presence after websocket is accepted
        await self.notify_user_online()
        await self.send_all_online_statuses()

        # ✅ Send initial online status to the connected user
        await self.send(text_data=json.dumps({
            "type": "user_online_status",
            "event_type": "user_online_status",
            "dialogue_slugs": [dialogue.slug for dialogue in dialogues],
            "user_id": self.user.id,
            "is_online": True
        }))

        # ✅ Send undelivered messages to the user
        for dialogue in dialogues:
            undelivered_messages = await sync_to_async(list)(
                dialogue.messages.filter(is_delivered=False).exclude(sender=self.user)
            )
            
            for message in undelivered_messages:
                try:
                    await self.mark_message_as_delivered(message)
                    content = await database_sync_to_async(get_message_content)(message, self.user)
                    is_encrypted = await database_sync_to_async(lambda: message.encryptions.exists())()
                    ...
                except Exception as e:
                    logger.exception("Failed to push an undelivered message on connect: %s", e)
                    continue

                await self.channel_layer.group_send(
                    f"dialogue_{dialogue.slug}",
                    {
                        "type": "chat_message",
                        "event_type": "chat_message",
                        "message_id": message.id,
                        "dialogue_slug": dialogue.slug,
                        "content": content,
                        "sender": {
                            "id": message.sender.id,
                            "username": message.sender.username,
                            "email": message.sender.email,
                        },
                        "timestamp": message.timestamp.isoformat(),
                        "is_encrypted": is_encrypted,
                        "is_delivered": True
                    }
                )
                await self.channel_layer.group_send(
                    f"user_{message.sender.id}",
                    {
                        "type": "mark_as_delivered",
                        "event_type": "mark_as_delivered",
                        "dialogue_slug": dialogue.slug,
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
                    "dialogue_slug": group.split("_", 1)[1],
                    "user_id": self.user.id,
                    "is_online": True
                }
            )


    # Force Logout -------------------------------------------------
    async def force_logout(self, event):
        user_id = event["user_id"]

        if user_id == self.user.id:
            self.force_logout_triggered = True
            await self.finalize_disconnect()
            await self.close()

    # Disconnect ---------------------------------------------------
    async def disconnect(self, close_code):
        # Immediately stop background loops
        self.connected = False

        # Cancel ping task ASAP
        if hasattr(self, "ping_task"):
            self.ping_task.cancel()
            from contextlib import suppress
            with suppress(asyncio.CancelledError):
                await self.ping_task

        if getattr(self, "force_logout_triggered", False):
            await self.finalize_disconnect()
            return

        # --- use per-connection key ---
        key = self._disc_key()

        # Clear any previous timer for THIS connection
        if DISCONNECT_TIMERS.get(key):
            DISCONNECT_TIMERS[key].cancel()
            del DISCONNECT_TIMERS[key]

        async def delayed_disconnect():
            await asyncio.sleep(10)
            # Only finalize if this connection did not come back
            if not getattr(self, "connected", False):
                await self.finalize_disconnect()

        DISCONNECT_TIMERS[key] = asyncio.create_task(delayed_disconnect())



    # Finalize Disconnect -----------------------------------------
    async def finalize_disconnect(self):
        if getattr(self, "_finalized", False):
            return
        self._finalized = True
        self.connected = False

        # 1) stop ping loop safely
        if hasattr(self, "ping_task"):
            self.ping_task.cancel()
            try:
                await self.ping_task
            except asyncio.CancelledError:
                pass

        # 2) mark this socket offline (Redis may set last_seen if it was last socket)
        await set_user_offline(self.user.id, self.channel_name)

        # 3) snapshot dialogue groups BEFORE discarding, for broadcasting
        groups = list(getattr(self, "group_names", []))

        # 4) leave all groups
        for g in groups:
            await self.channel_layer.group_discard(g, self.channel_name)
        await self.channel_layer.group_discard(f"user_{self.user.id}", self.channel_name)
        if getattr(self, "device_id", None):
            await self.channel_layer.group_discard(f"device_{self.device_id}", self.channel_name)

        # 5) notify others: went offline (presence event)
        for g in groups:
            await self.channel_layer.group_send(
                g,
                {
                    "type": "user_online_status",
                    "event_type": "user_online_status",
                    "dialogue_slug": g.split("_", 1)[1],
                    "user_id": self.user.id,
                    "is_online": False,
                }
            )

        # 6) cleanup timers
        if TYPING_TIMEOUTS.get(self.user.id):
            TYPING_TIMEOUTS[self.user.id].cancel()
            del TYPING_TIMEOUTS[self.user.id]

        key = self._disc_key()
        if DISCONNECT_TIMERS.get(key):
            DISCONNECT_TIMERS[key].cancel()
            del DISCONNECT_TIMERS[key]

        # 7) if truly fully-offline now, broadcast last_seen with epoch
        try:
            # re-check presence after cleanup
            statuses = await get_online_status_for_users([self.user.id])
            fully_offline = not bool(statuses.get(self.user.id, False))

            if fully_offline:
                # read epoch from Redis (set by set_user_offline if last socket)
                last_seen_ts = await get_last_seen(self.user.id)

                # fallback: set now if still missing
                if not last_seen_ts:
                    last_seen_ts = int(time.time())
                    redis_conn = await get_redis_connection()
                    await redis_conn.set(f"last_seen:{self.user.id}", last_seen_ts)
                    await redis_conn.close()

                # build ISO with UTC tz
                last_seen_dt = datetime.fromtimestamp(last_seen_ts, tz=timezone.utc)
                # keep legacy display for older clients; frontend should compute itself
                last_seen_display = timesince(last_seen_dt)  # humanized on backend (optional)

                for g in groups:
                    await self.channel_layer.group_send(
                        g,
                        {
                            "type": "user_last_seen",
                            "dialogue_slug": g.split("_", 1)[1],
                            "user_id": self.user.id,
                            "is_online": False,                 # <- new
                            "last_seen_epoch": last_seen_ts,    # <- new (seconds)
                            "last_seen": last_seen_dt.isoformat(),
                            "last_seen_display": last_seen_display,
                        }
                    )
        except Exception as e:
            logger.error(f"[finalize_disconnect] failed to broadcast last_seen: {e}")
            # swallow to avoid crashing disconnect flow
            pass

        
    # Start Ping ---------------------------
    async def start_ping(self):
        try:
            while self.connected:
                # If presence says online, send a lightweight ping
                try:
                    online_statuses = await get_online_status_for_users([self.user.id])
                    if online_statuses.get(self.user.id, False):
                        await self.send(text_data=json.dumps({
                            "type": "ping",
                            "timestamp": datetime.now().isoformat()
                        }))
                except Exception as send_err:
                    # Socket likely closed; stop the loop to avoid 'send after close'
                    logger.warning("[start_ping] send failed, stopping ping loop: %s", send_err)
                    break

                await asyncio.sleep(30)
        except asyncio.CancelledError:
            # Task canceled on disconnect; this is expected
            pass
        except Exception as e:
            # Any unexpected error: log once and exit loop
            logger.error("[start_ping] Unexpected error (exiting): %s", e)

    # -----------------------------------------------------------
    def _disc_key(self) -> Tuple[int, str]:
        """Unique key for this specific websocket connection."""
        return (self.user.id, self.channel_name)

    # Receive ---------------------------------------------------
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
            
            if data.get("type") == "mark_as_delivered":
                await self.handle_mark_as_delivered(data)
                return


            if data.get("type") == "request_online_status":
                dialogue_slug = data.get("dialogue_slug")
                if not dialogue_slug:
                    return

                dialogue = await sync_to_async(Dialogue.objects.get)(slug=dialogue_slug)
                participants = await sync_to_async(list)(dialogue.participants.all())
                participant_ids = [participant.id for participant in participants]
                online_statuses = await get_online_status_for_users(participant_ids)

                for participant in participants:
                    online_status = online_statuses.get(participant.id, False)
                    await self.send(text_data=json.dumps({
                        "type": "user_online_status",
                        "event_type": "user_online_status",
                        "dialogue_slug": dialogue_slug,
                        "user_id": participant.id,
                        "is_online": online_status
                    }))
                    
        except Exception as e:
            await self.send_json({"type": "error", "message": str(e)})



    # User Online ---------------------------
    async def notify_user_online(self):
        # ✅ Deliver undelivered messages and notify their senders
        undelivered_messages = await sync_to_async(list)(
            Message.objects.filter(is_delivered=False, dialogue__participants=self.user)
        )
        for message in undelivered_messages:
            await self.mark_message_as_delivered(message)
            await self.notify_message_delivered_to_sender(message)

        # ✅ Notify all group members about user's online status
        for group in self.group_names:
            await self.channel_layer.group_send(
                group,
                {
                    "type": "user_online_status",
                    "event_type": "user_online_status",
                    "dialogue_slug": group.split("_", 1)[1],
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
                "dialogue_slug": message.dialogue.slug,
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
                    "dialogue_slug": group.split("_", 1)[1],
                    "user_id": self.user.id,
                    "is_online": False
                }
            )


    # Online Status ---------------------------
    async def user_online_status(self, event):
        await self.send(text_data=json.dumps({
            "type": "user_online_status",
            "event_type": "user_online_status",
            "dialogue_slug": event["dialogue_slug"],
            "user_id": event["user_id"],
            "is_online": event["is_online"]
        }))

    # Send All Online Status ---------------------------
    async def send_all_online_statuses(self):
        dialogues = await sync_to_async(list)(Dialogue.objects.filter(participants=self.user))
        for dialogue in dialogues:
            participants = await sync_to_async(list)(dialogue.participants.all())
            ids = [p.id for p in participants]
            online_statuses = await get_online_status_for_users(ids)  # ✅ معتبر و همراه با کلین‌آپ

            for participant in participants:
                is_online = bool(online_statuses.get(participant.id, False))
                await self.send(text_data=json.dumps({
                    "type": "user_online_status",
                    "event_type": "user_online_status",
                    "dialogue_slug": dialogue.slug,
                    "user_id": participant.id,
                    "is_online": is_online
                }))
            
    # Typing Status ----------------------
    async def handle_typing_status(self, data):
        dialogue_slug = data.get("dialogue_slug")
        is_typing = data.get("is_typing", False)

        if not dialogue_slug:
            return

        await self.channel_layer.group_send(
            f"dialogue_{dialogue_slug}",
            {
                "type": "typing_status",
                "event_type": "typing_status",
                "dialogue_slug": dialogue_slug,
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
            TYPING_TIMEOUTS[self.user.id] = asyncio.create_task(self.clear_typing_status(dialogue_slug))


    # Delete Typing Status after 5 sec ----------------------
    async def clear_typing_status(self, dialogue_slug):
        await asyncio.sleep(5)
        await self.channel_layer.group_send(
            f"dialogue_{dialogue_slug}",
            {
                "type": "typing_status",
                "event_type": "typing_status",
                "dialogue_slug": dialogue_slug,
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
        dialogue_slug = (data.get("dialogue_slug") or "").strip()
        is_encrypted = bool(data.get("is_encrypted", False))
        encrypted_contents = data.get("encrypted_contents", [])

        if not dialogue_slug:
            await self.send_json({"type": "error", "code": "BAD_REQUEST", "message": "dialogue_slug is required"})
            return

        try:
            dialogue = await sync_to_async(Dialogue.objects.get)(slug=dialogue_slug, participants=self.user)
        except Dialogue.DoesNotExist:
            await self.send_json({"type": "error", "code": "NOT_FOUND", "message": "Dialogue not found"})
            return

        is_group = bool(dialogue.is_group)

        # Enforce sender PoP for DMs (configurable in settings)
        verified = await database_sync_to_async(is_sender_device_verified)(
            self.user, self.device_id, dialogue_is_group=is_group
        )
        if not verified:
            await self.send_json({
                "type": "error",
                "code": "SENDER_DEVICE_UNVERIFIED",
                "message": "Sender device is not verified"
            })
            return

        # Policy alignment:
        # - Group: MUST NOT be client-encrypted
        # - DM: MUST be client-encrypted
        if is_group and is_encrypted:
            await self.send_json({"type": "error", "code": "BAD_REQUEST", "message": "Group messages must not be encrypted"})
            return
        if (not is_group) and (not is_encrypted):
            await self.send_json({"type": "error", "code": "BAD_REQUEST", "message": "DM messages must be encrypted"})
            return

        try:
            if is_group:
                # Expect plaintext in encrypted_contents[0].encrypted_content
                plain_message = (encrypted_contents[0].get("encrypted_content") if encrypted_contents and isinstance(encrypted_contents, list) else "") or ""
                plain_message = plain_message.strip()
                if not plain_message:
                    await self.send_json({"type": "error", "code": "BAD_REQUEST", "message": "Empty content"})
                    return

                base64_str = base64.b64encode(plain_message.encode("utf-8")).decode("utf-8")
                content_bytes = base64_str.encode("utf-8")

                message = await sync_to_async(Message.objects.create)(
                    dialogue=dialogue,
                    sender=self.user,
                    content_encrypted=content_bytes,
                )

            else:
                # DM: E2EE required
                if not isinstance(encrypted_contents, list) or not encrypted_contents:
                    await self.send_json({"type": "error", "code": "BAD_REQUEST", "message": "encrypted_contents must be a non-empty list"})
                    return

                # Sanitize & dedupe by device_id (first occurrence wins)
                seen = set()
                clean_items = []
                for item in encrypted_contents:
                    dev = (str(item.get("device_id") or "").strip().lower())
                    enc = item.get("encrypted_content")
                    if not dev or not isinstance(enc, str) or not enc:
                        continue
                    if dev in seen:
                        continue
                    seen.add(dev)
                    clean_items.append({"device_id": dev, "encrypted_content": enc})

                if not clean_items:
                    await self.send_json({"type": "error", "code": "BAD_REQUEST", "message": "No valid encrypted contents"})
                    return

                message = await sync_to_async(Message.objects.create)(
                    dialogue=dialogue,
                    sender=self.user,
                    content_encrypted=b"[Encrypted]",
                )

                # Optional safety bound
                MAX_PER_MESSAGE = 500
                to_create = [
                    MessageEncryption(message=message, device_id=it["device_id"], encrypted_content=it["encrypted_content"])
                    for it in clean_items[:MAX_PER_MESSAGE]
                ]
                await sync_to_async(MessageEncryption.objects.bulk_create)(to_create)

            # Update dialogue metadata
            dialogue.last_message = message
            await sync_to_async(dialogue.save)(update_fields=["last_message"])

        except Exception as e:
            await self.send_json({"type": "error", "message": "Failed to save message", "details": str(e)})
            return

        # Self-destruct hook (unchanged)
        await self.handle_self_destruct_messages()

        # Broadcast
        participants = await sync_to_async(list)(dialogue.participants.all())
        user_ids = [p.id for p in participants if p.id != self.user.id]
        online_statuses = await get_online_status_for_users(user_ids)

        if is_group:
            # Plain (server-encoded)
            plain_message = base64.b64decode(message.content_encrypted).decode("utf-8")
            for participant in participants:
                is_delivered = online_statuses.get(participant.id, False)
                await self.channel_layer.group_send(
                    f"user_{participant.id}",
                    {
                        "type": "chat_message",
                        "event_type": "chat_message",
                        "message_id": message.id,
                        "dialogue_slug": dialogue_slug,
                        "content": plain_message,
                        "sender": {
                            "id": self.user.id,
                            "username": self.user.username,
                            "email": self.user.email,
                        },
                        "timestamp": message.timestamp.isoformat(),
                        "is_encrypted": False,
                        "encrypted_for_device": None,
                        "is_delivered": is_delivered,
                    }
                )
                if is_delivered:
                    await self.mark_message_as_delivered(message)
                else:
                    deliver_offline_message.delay(message.id)
                await self.channel_layer.group_send(f"user_{participant.id}", {"type": "trigger_unread_count_update"})
        else:
            # DM: per-device broadcast for which we actually have envelopes
            enc_rows = await sync_to_async(list)(MessageEncryption.objects.filter(message=message).values("device_id", "encrypted_content"))

            for enc in enc_rows:
                device_id = enc["device_id"]
                # Resolve participant by device_id (optional optimization: map device->user)
                # We keep delivery mark per recipient user; compute from online_statuses if you want.
                await self.channel_layer.group_send(
                    f"device_{device_id}",
                    {
                        "type": "chat_message",
                        "event_type": "chat_message",
                        "message_id": message.id,
                        "dialogue_slug": dialogue_slug,
                        "content": enc["encrypted_content"],
                        "sender": {
                            "id": self.user.id,
                            "username": self.user.username,
                            "email": self.user.email,
                        },
                        "timestamp": message.timestamp.isoformat(),
                        "is_encrypted": True,
                        "encrypted_for_device": device_id,
                        "is_delivered": False,  # if you have per-device online info, set accordingly
                    }
                )
            # Delivery bookkeeping (keep your existing policy)
            for participant in participants:
                is_delivered = online_statuses.get(participant.id, False)
                if is_delivered:
                    await self.mark_message_as_delivered(message)
                else:
                    deliver_offline_message.delay(message.id)
                await self.channel_layer.group_send(f"user_{participant.id}", {"type": "trigger_unread_count_update"})




    # Save Message ----------------------
    @sync_to_async
    def save_message(self, dialogue_slug, content, is_encrypted):
        dialogue = Dialogue.objects.get(slug=dialogue_slug)   
            
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


    # ---------------------------------------------------
    async def handle_self_destruct_messages(self):
        messages_to_delete = await sync_to_async(Message.objects.filter)(
            sender=self.user,
            self_destruct_at__lte=datetime.now()
        )
        await sync_to_async(messages_to_delete.delete)()

    # ---------------------------------------------------
    async def chat_message(self, event):
        event["type"] = "chat_message"
        await self.send(text_data=json.dumps(event))
        
    # ---------------------------------------------------
    async def typing_status(self, event):
        await self.send(text_data=json.dumps({
            "type": "typing_status",
            "event_type": "typing_status",
            "dialogue_slug": event["dialogue_slug"],
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
            # idempotent helper (OK if already delivered)
            await mark_message_as_delivered_atomic(message)

            # ✅ notify current socket (whoever is running this - may be sender or recipient)
            await self.send(text_data=json.dumps({
                "type": "mark_as_delivered",
                "event_type": "mark_as_delivered",
                "dialogue_slug": message.dialogue.slug,
                "message_id": message.id,
                "user_id": recipient.id,
                "is_delivered": True
            }))

            # ✅ notify ALL sessions of the sender
            await self.channel_layer.group_send(
                f"user_{message.sender.id}",
                {
                    "type": "mark_as_delivered",
                    "event_type": "mark_as_delivered",
                    "dialogue_slug": message.dialogue.slug,
                    "message_id": message.id,
                    "user_id": recipient.id,
                    "is_delivered": True
                }
            )



    # Mark as Delivered Message and send to Sender User --------------------------------------------
    async def mark_as_delivered(self, event):
        await self.send(text_data=json.dumps({
            "type": "mark_as_delivered",
            "dialogue_slug": event["dialogue_slug"],
            "message_id": event["message_id"],
            "user_id": event["user_id"],
            "is_delivered": True,
        }))


         
    # Mark as Read Real-Time Update ----------------------------------------------------------------
    async def mark_message_as_read(self, data):
        dialogue_slug = data.get("dialogue_slug")
        if not dialogue_slug:
            return

        dialogue = await sync_to_async(Dialogue.objects.get)(slug=dialogue_slug)
        unread_messages = await sync_to_async(list)(
            Message.objects.filter(dialogue=dialogue).exclude(seen_by_users=self.user)
        )

        for message in unread_messages:
            if message.sender_id == self.user.id:
                continue 
            await mark_message_as_read_atomic(message, self.user)

        await self.channel_layer.group_send(
            f"dialogue_{dialogue_slug}",
            {
                "type": "mark_as_read",
                "event_type": "mark_as_read",
                "dialogue_slug": dialogue_slug,
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


    # Mark as Delivered Handler ----------
    async def handle_mark_as_delivered(self, data):
        dialogue_slug = data.get("dialogue_slug")
        message_id = data.get("message_id")
        if not dialogue_slug or not message_id:
            return

        # validate membership and load objects
        dialogue = await sync_to_async(Dialogue.objects.get)(slug=dialogue_slug, participants=self.user)
        message  = await sync_to_async(Message.objects.get)(id=message_id, dialogue=dialogue)

        # only the recipient can mark delivered
        if message.sender_id == self.user.id:
            return  # silently ignore

        # idempotent: skip if already delivered
        if message.is_delivered:
            return

        # mark delivered (atomic helper if you have it)
        await mark_message_as_delivered_atomic(message)

        # notify sender (their all sessions)
        await self.channel_layer.group_send(
            f"user_{message.sender_id}",
            {
                "type": "mark_as_delivered",
                "dialogue_slug": dialogue.slug,
                "message_id": message.id,
                "user_id": self.user.id,  # recipient
            }
        )

        
    
    # Handle File Messages ----------------------
    async def handle_file_message(self, data):
        dialogue_slug = data.get("dialogue_slug")
        message_id = data.get("message_id")  
        file_type = data.get("file_type")
        file_url = data.get("file_url")

        if not dialogue_slug or not message_id or not file_type or not file_url:
            return

        try:
            # Get message via dialogue slug and message ID
            message = await sync_to_async(
                lambda: Message.objects.select_related("dialogue").get(id=message_id, dialogue__slug=dialogue_slug)
            )()
        except Message.DoesNotExist:
            return

        dialogue = message.dialogue
        is_group = bool(dialogue.is_group)

        # Enforce PoP for DMs (broadcast path)
        verified = await database_sync_to_async(is_sender_device_verified)(
            self.user, self.device_id, dialogue_is_group=is_group
        )
        if not verified:
            await self.send_json({"type": "error", "code": "SENDER_DEVICE_UNVERIFIED", "message": "Sender device is not verified"})
            return

        sender = await sync_to_async(lambda: {
            "id": message.sender.id,
            "username": message.sender.username,
            "email": message.sender.email,
        })()

        # Get all participants (excluding sender)
        participants = await sync_to_async(
            lambda: list(message.dialogue.participants.exclude(id=message.sender.id).values_list("id", flat=True))
        )()

        for user_id in participants:
            
            
            # is_encrypted_file معمولاً فیلد مدل است → دسترسی مستقیم OK
            is_encrypted_file = message.is_encrypted_file

            # ولی is_encrypted پراپرتی است → امنش کن
            is_encrypted = await database_sync_to_async(lambda: message.encryptions.exists())()

            await self.channel_layer.group_send(
                f"user_{user_id}",
                {
                    "type": "file_message",
                    "event_type": "file_message",
                    "message_id": message.id,
                    "dialogue_slug": dialogue_slug,
                    "file_type": file_type,
                    "file_url": file_url,
                    "sender": sender,
                    "timestamp": message.timestamp.isoformat(),
                    "is_encrypted_file": is_encrypted_file,
                    "is_encrypted": is_encrypted,  # ✅
                }
            )


    # Handle File Canceled Message ----------------------
    async def handle_upload_canceled(self, data):
        dialogue_slug = data.get("dialogue_slug")
        file_type = data.get("file_type")

        if not dialogue_slug or not file_type:
            return

        try:
            dialogue = await sync_to_async(Dialogue.objects.get)(slug=dialogue_slug)
        except Dialogue.DoesNotExist:
            return

        # ✅ Notify all participants via group that upload was canceled
        await self.channel_layer.group_send(
            f"dialogue_{dialogue_slug}",
            {
                "type": "file_upload_status",
                "event_type": "file_upload_status",
                "dialogue_slug": dialogue_slug,
                "file_type": file_type,
                "status": "cancelled",
                "progress": 0,
            }
        )

        # ✅ Confirm cancel to sender
        await self.send(text_data=json.dumps({
            "type": "upload_canceled",
            "dialogue_slug": dialogue_slug,
            "file_type": file_type,
            "status": "cancelled"
        }))




    # File Message Event to User ----------------------
    async def file_message(self, event):
        await self.send(text_data=json.dumps(event))
        
            
    # ارسال وضعیت ارسال فایل (در حال آپلود، در حال پردازش، آماده ارسال) ----------------------------------------------
    async def send_file_status(self, dialogue_slug, file_type, status, progress=None):
        try:
            dialogue = await sync_to_async(Dialogue.objects.get)(slug=dialogue_slug)
        except Dialogue.DoesNotExist:
            return

        await self.channel_layer.group_send(
            f"dialogue_{dialogue_slug}",
            {
                "type": "file_upload_status",
                "event_type": "file_upload_status",
                "dialogue_slug": dialogue_slug,
                "sender": {
                    "id": self.user.id,
                    "username": self.user.username,
                    "email": self.user.email,
                },
                "file_type": file_type,
                "status": status,
                "progress": progress,
            }
        )
   
    async def handle_file_upload_status(self, data):
        dialogue_slug = data.get("dialogue_slug")
        file_type = data.get("file_type")
        status = data.get("status")
        progress = data.get("progress", None)

        if not dialogue_slug or not file_type or not status:
            return

        await self.send_file_status(dialogue_slug, file_type, status, progress)

        
    async def handle_recording_status(self, data):
        dialogue_slug = data.get("dialogue_slug")
        is_recording = data.get("is_recording", False)
        file_type = data.get("file_type")  # "audio" or "video"

        if not dialogue_slug or not file_type:
            return

        try:
            dialogue = await sync_to_async(Dialogue.objects.get)(slug=dialogue_slug)
        except Dialogue.DoesNotExist:
            return

        await self.channel_layer.group_send(
            f"dialogue_{dialogue_slug}",
            {
                "type": "recording_status",
                "event_type": "recording_status",
                "dialogue_slug": dialogue_slug,
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
        is_encrypted = bool(data.get("is_encrypted", False))
        encrypted_contents = data.get("encrypted_contents", [])
        new_content = (data.get("new_content") or "").strip()

        if not message_id:
            return

        try:
            message = await sync_to_async(Message.objects.select_related("dialogue").get)(id=message_id)
        except Message.DoesNotExist:
            return

        if message.sender_id != self.user.id:
            return

        dialogue = message.dialogue
        dialogue_slug = dialogue.slug
        is_group = bool(dialogue.is_group)
        now = timezone.now()

        # Enforce PoP for DMs
        verified = await database_sync_to_async(is_sender_device_verified)(
            self.user, self.device_id, dialogue_is_group=is_group
        )
        if not verified:
            await self.send_json({"type": "error", "code": "SENDER_DEVICE_UNVERIFIED", "message": "Sender device is not verified"})
            return

        if is_group:
            if not new_content:
                return
            base64_str = base64.b64encode(new_content.encode("utf-8")).decode("utf-8")
            content_bytes = base64_str.encode("utf-8")

            await sync_to_async(setattr)(message, "content_encrypted", content_bytes)
            await sync_to_async(setattr)(message, "is_edited", True)
            await sync_to_async(setattr)(message, "edited_at", now)
            await sync_to_async(setattr)(message, "encrypted_for_device", None)
            await sync_to_async(setattr)(message, "aes_key_encrypted", None)
            await sync_to_async(message.save)()

        else:
            if not isinstance(encrypted_contents, list) or not encrypted_contents:
                await self.send_json({"type": "error", "code": "BAD_REQUEST", "message": "encrypted_contents required for DM edit"})
                return

            # Sanitize & dedupe envelopes
            seen = set()
            clean_items = []
            for item in encrypted_contents:
                dev = (str(item.get("device_id") or "").strip().lower())
                enc = item.get("encrypted_content")
                if not dev or not isinstance(enc, str) or not enc:
                    continue
                if dev in seen:
                    continue
                seen.add(dev)
                clean_items.append({"device_id": dev, "encrypted_content": enc})

            if not clean_items:
                await self.send_json({"type": "error", "code": "BAD_REQUEST", "message": "No valid encrypted contents"})
                return

            await sync_to_async(MessageEncryption.objects.filter(message=message).delete)()
            await sync_to_async(setattr)(message, "content_encrypted", b"[Encrypted]")
            await sync_to_async(setattr)(message, "is_edited", True)
            await sync_to_async(setattr)(message, "edited_at", now)
            await sync_to_async(message.save)()

            MAX_PER_MESSAGE = 500
            to_create = [
                MessageEncryption(message=message, device_id=it["device_id"], encrypted_content=it["encrypted_content"])
                for it in clean_items[:MAX_PER_MESSAGE]
            ]
            await sync_to_async(MessageEncryption.objects.bulk_create)(to_create)

        # Update last_message
        dialogue.last_message = message
        await sync_to_async(dialogue.save)(update_fields=["last_message"])

        # Broadcast edits
        participants = await sync_to_async(list)(dialogue.participants.all())

        if is_group:
            for participant in participants:
                await self.channel_layer.group_send(
                    f"user_{participant.id}",
                    {
                        "type": "edit_message",
                        "message_id": message.id,
                        "dialogue_slug": dialogue_slug,
                        "new_content": new_content,
                        "edited_at": now.isoformat(),
                        "is_encrypted": False,
                        "is_edited": True,
                        "sender": {
                            "id": message.sender.id,
                            "username": message.sender.username,
                        },
                    }
                )
        else:
            enc_rows = await sync_to_async(list)(MessageEncryption.objects.filter(message=message).values("device_id", "encrypted_content"))
            for enc in enc_rows:
                await self.channel_layer.group_send(
                    f"device_{enc['device_id']}",
                    {
                        "type": "edit_message",
                        "message_id": message.id,
                        "dialogue_slug": dialogue_slug,
                        "edited_at": now.isoformat(),
                        "is_encrypted": True,
                        "is_edited": True,
                        "encrypted_contents": [{
                            "device_id": enc["device_id"],
                            "encrypted_content": enc["encrypted_content"],
                        }],
                        "sender": {
                            "id": message.sender.id,
                            "username": message.sender.username,
                        },
                    }
                )



    # Handle Real-Time Edit Update ----------------------------------------------
    async def edit_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "edit_message",
            "message_id": event["message_id"],
            "dialogue_slug": event["dialogue_slug"],
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

            dialogue_slug = dialogue.slug
            await sync_to_async(message.delete)()

            # ✅ به همه کاربران گفتگو
            await self.channel_layer.group_send(
                f"dialogue_{dialogue_slug}",
                {
                    "type": "message_hard_deleted",
                    "dialogue_slug": dialogue_slug,
                    "message_id": message_id,
                }
            )

            # ✅ به فرستنده (مستقیم)
            await self.send(text_data=json.dumps({
                "type": "message_hard_deleted",
                "dialogue_slug": dialogue_slug,
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
            "dialogue_slug": event["dialogue_slug"],
            "message_id": event["message_id"],
        }))

    # Last Seen -----------------------------------------------------------------
    async def user_last_seen(self, event):
        # Send both ISO and epoch so frontend can compute relative time consistently
        await self.send(text_data=json.dumps({
            "type": "user_last_seen",
            "dialogue_slug": event["dialogue_slug"],
            "user_id": event["user_id"],
            "is_online": event.get("is_online", False), 
            "last_seen": event.get("last_seen"),          # ISO datetime or null
            "last_seen_epoch": event.get("last_seen_epoch"),  # new field (unix ts)
            "last_seen_display": event.get("last_seen_display"),  # legacy
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
            "dialogue_slug": event["dialogue_slug"],
        })
        
    # Founder Transferred -------------------------------------------------------
    async def founder_transferred(self, event):
        await self.send_json({
            "type": "founder_transferred",
            "dialogue_slug": event["dialogue_slug"],
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
                "dialogue_slug": dialogue.slug,
                "unread_count": unread_count
            })

        await self.send_json({
            "type": "unread_count_update",
            "payload": results
        })


    async def trigger_unread_count_update(self, event):
        await self.send_unread_counts()