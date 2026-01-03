# apps/conversation/realtime/handler.py
import asyncio
import json
import time
import logging
from datetime import datetime
from django.utils import timezone
from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from django.utils import timezone
from django.utils.timesince import timesince
from django.contrib.auth import get_user_model

from apps.accounts.models import UserDeviceKey
from apps.conversation.models import Dialogue
from apps.conversation.utils import get_message_content
from services.redis_online_manager import (
    set_user_online,
    set_user_offline,
    refresh_user_connection,
    get_online_status_for_users,
    get_last_seen,
    get_redis_connection,
)

# ---- Mixins ----------------------------------------------------
from apps.conversation.realtime.mixins.presence import PresenceMixin
from apps.conversation.realtime.mixins.typing import TypingMixin, TYPING_TIMEOUTS
from apps.conversation.realtime.mixins.delivery import DeliveryMixin
from apps.conversation.realtime.mixins.files import FileEventsMixin
from apps.conversation.realtime.mixins.edits import EditDeleteMixin
from apps.conversation.realtime.mixins.message import MessageMixin
from apps.conversation.realtime.mixins.read import ReadMixin
from apps.conversation.realtime.mixins.group_events import ConversationGroupMixin

logger = logging.getLogger(__name__)
User = get_user_model()


# =================================================================
#   ConversationHandler
#   (former DialogueConsumer logic, now wrapped for central consumer)
# =================================================================
class ConversationHandler(
    MessageMixin,
    PresenceMixin,
    TypingMixin,
    DeliveryMixin,
    FileEventsMixin,
    EditDeleteMixin,
    ReadMixin,
    ConversationGroupMixin,
):
    def __init__(self, consumer):
        self.consumer = consumer

        # Forward essential fields so mixins can access them
        self.user = consumer.user
        self.device_id = consumer.device_id
        self.scope = consumer.scope
        self.channel_layer = consumer.channel_layer
        self.channel_name = consumer.channel_name

        # Flags
        self.connected = False
        self._finalized = False
        self.force_logout_triggered = False
        self.ping_task = None

        # Dialogue maps
        self.slug = None
        self.group_names = set()
        self.dialogue_map = {}

        # 🔥 VERY IMPORTANT: initialize mixins
        MessageMixin.__init__(self)
        PresenceMixin.__init__(self)
        TypingMixin.__init__(self)
        DeliveryMixin.__init__(self)
        FileEventsMixin.__init__(self)
        EditDeleteMixin.__init__(self)
        ReadMixin.__init__(self)
        ConversationGroupMixin.__init__(self)


    # --------------------------------------------------------------
    # CONNECT
    # --------------------------------------------------------------
    async def connect(self):
        # Pull identity from central consumer
        self.user = self.consumer.user
        self.device_id = self.consumer.device_id
        self.connected = True

        # Dialogue slug (only this should be read from scope)
        self.slug = self.scope.get("url_route", {}).get("kwargs", {}).get("slug")

        # Auth guard
        if not self.user or not self.user.is_authenticated or not self.device_id:
            await self.consumer.close()
            return

        # Device verification
        belongs = await database_sync_to_async(
            UserDeviceKey.objects.filter(
                user=self.user, device_id=self.device_id, is_active=True
            ).exists
        )()
        if not belongs:
            await self.consumer.close(code=4403)
            return

        # Mark this socket online in Redis
        try:
            await set_user_online(self.user.id, self.channel_name)
        except Exception as e:
            logger.error(f"[Redis] set_user_online failed: {e}")

        # SAFE group_add
        try:
            await self.channel_layer.group_add(f"user_{self.user.id}", self.channel_name)
        except Exception as e:
            logger.error(f"[Redis] group_add user failed: {e}")

        try:
            await self.channel_layer.group_add(f"device_{self.device_id}", self.channel_name)
        except Exception as e:
            logger.error(f"[Redis] group_add device failed: {e}")

        # Load all dialogues for user (always)
        dialogues = await sync_to_async(list)(
            Dialogue.objects.filter(participants=self.user)
        )

        dialogue_slugs = {d.slug for d in dialogues}
        if self.slug and self.slug not in dialogue_slugs:
            await self.consumer.close()
            return

        # Build map
        self.dialogue_map = {f"dialogue_{d.slug}": d.id for d in dialogues}

        # Join dialogue groups
        self.group_names = set(self.dialogue_map.keys())

        for group_name in self.group_names:
            try:
                await self.channel_layer.group_add(group_name, self.channel_name)
                await self.consumer.join_feature_group(group_name)
            except Exception as e:
                logger.error(f"[Redis] group_add dialogue failed ({group_name}): {e}")


        # Presence updates
        await self.notify_user_online()
        await self.send_all_online_statuses()

        # Notify connected user (UNIFIED)
        await self.consumer.safe_send_json({
            "type": "event",
            "app": "conversation",
            "event": "user_online_status",
            "data": {
                "dialogue_slugs": [d.slug for d in dialogues],
                "user_id": self.user.id,
                "is_online": True,
            }
        })

        # Send undelivered messages to user
        await self._push_undelivered_messages(dialogues)

        # Broadcast presence to dialogue groups (UNIFIED)
        for group in self.group_names:
            await self.channel_layer.group_send(
                group,
                {
                    "type": "dispatch_event",
                    "app": "conversation",
                    "event": "user_online_status",
                    "data": {
                        "dialogue_slug": group.split("_", 1)[1],
                        "user_id": self.user.id,
                        "is_online": True,
                    },
                },
            )


    # --------------------------------------------------------------
    # DISCONNECT
    # --------------------------------------------------------------
    async def on_disconnect(self):
        # Central calls this without args
        await self.disconnect(1000)


    # --------------------------------------------------------------
    # Push Undelivered Messages
    # --------------------------------------------------------------
    async def _push_undelivered_messages(self, dialogues):
        for dialogue in dialogues:
            # Messages that were sent to ME while I was offline (or not delivered yet)
            undelivered = await sync_to_async(list)(
                dialogue.messages
                    .select_related("sender") 
                    .filter(is_delivered=False)
                    .exclude(sender=self.user)
            )

            for msg in undelivered:
                try:
                    # 1) Mark delivered in DB (atomic)
                    await self.mark_message_as_delivered(msg)

                    # 2) Detect DM E2EE (encryption rows exist)
                    has_encryptions = await database_sync_to_async(
                        lambda: msg.encryptions.exists()
                    )()

                    # 3) Build payload
                    payload = {
                        "message_id": msg.id,
                        "dialogue_slug": dialogue.slug,
                        "sender": {
                            "id": msg.sender.id,
                            "username": msg.sender.username,
                            "email": msg.sender.email,
                        },
                        "timestamp": msg.timestamp.isoformat(),
                        "is_delivered": True,
                        "is_system": getattr(msg, "is_system", False),
                        "system_event": getattr(msg, "system_event", None),
                    }

                    # -------------------------------------------------
                    # IMPORTANT RULE:
                    # - If E2EE DM: NEVER decrypt on backend. Send encrypted payload for this device only.
                    # - Else: backend can send decrypted/plain text.
                    # -------------------------------------------------

                    if has_encryptions:
                        # ✅ E2EE DM replay (NO backend decrypt)
                        device_id = getattr(self, "device_id", None)

                        enc_row = None
                        if device_id:
                            enc_row = await database_sync_to_async(
                                lambda: msg.encryptions.filter(device_id=device_id).first()
                            )()

                        payload.update({
                            "is_encrypted": True,
                            "content": enc_row.encrypted_content if enc_row else None,
                            "encrypted_for_device": device_id,
                            "decrypted_content": None,
                        })

                    else:
                        # ✅ Non-E2EE replay (backend can safely provide plain text)
                        content = await database_sync_to_async(get_message_content)(msg, self.user)

                        payload.update({
                            "is_encrypted": False,
                            "decrypted_content": content,
                            "content": None,
                            "encrypted_for_device": None,
                        })

                except Exception as e:
                    logger.exception("Failed to push undelivered message: %s", e)
                    continue

                # 4) Send chat_message to receiver (me) via dialogue group
                await self.channel_layer.group_send(
                    f"dialogue_{dialogue.slug}",
                    {
                        "type": "dispatch_event",
                        "app": "conversation",
                        "event": "chat_message",
                        "data": payload,
                    },
                )

                # 5) Notify original sender that this message is delivered
                await self.channel_layer.group_send(
                    f"user_{msg.sender.id}",
                    {
                        "type": "dispatch_event",
                        "app": "conversation",
                        "event": "mark_as_delivered",
                        "data": {
                            "dialogue_slug": dialogue.slug,
                            "message_id": msg.id,
                            "user_id": self.user.id,
                        },
                    },
                )


    # --------------------------------------------------------------
    # Force Logout
    # --------------------------------------------------------------
    async def force_logout(self, event):
        # Defensive read
        if int(event.get("user_id") or 0) == self.user.id:
            self.force_logout_triggered = True
            await self.finalize_disconnect()
            await self.consumer.close()


    # --------------------------------------------------------------
    # DISCONNECT
    # --------------------------------------------------------------
    async def disconnect(self, close_code):
        self.connected = False

        # Forced-logout path
        if getattr(self, "force_logout_triggered", False):
            await self.finalize_disconnect()
            return

        # No local timers; finalize immediately (Redis decides fully-offline)
        await self.finalize_disconnect()



    # --------------------------------------------------------------
    # FINALIZE DISCONNECT
    # --------------------------------------------------------------
    async def finalize_disconnect(self):
        if getattr(self, "_finalized", False):
            return
        self._finalized = True
        self.connected = False

        # Mark this socket offline in Redis
        try:
            await set_user_offline(self.user.id, self.channel_name)
        except Exception as e:
            logger.error(f"[Redis] set_user_offline failed: {e}")

        # Snapshot groups (for this socket)
        groups = list(getattr(self, "group_names", []))

        # Leave WS groups (socket-level cleanup)
        for g in groups:
            try:
                await self.channel_layer.group_discard(g, self.channel_name)
            except Exception as e:
                logger.error(f"[Redis] group_discard failed ({g}): {e}")

        try:
            await self.channel_layer.group_discard(f"user_{self.user.id}", self.channel_name)
        except Exception as e:
            logger.error(f"[Redis] group_discard user failed: {e}")

        if getattr(self, "device_id", None):
            try:
                await self.channel_layer.group_discard(f"device_{self.device_id}", self.channel_name)
            except Exception:
                pass

        # Cleanup typing timeouts
        if TYPING_TIMEOUTS.get(self.user.id):
            TYPING_TIMEOUTS[self.user.id].cancel()
            del TYPING_TIMEOUTS[self.user.id]


        # Check if user is still online on another device (Redis is source of truth)
        fully_offline = False
        try:
            statuses = await get_online_status_for_users([self.user.id])
            fully_offline = not bool(statuses.get(self.user.id, False))
        except Exception:
            # If Redis check fails, avoid false offline broadcast
            fully_offline = False

        if not fully_offline:
            return  # User still online elsewhere -> do NOT broadcast offline/last_seen


        # Broadcast offline presence (unified format)
        for g in groups:
            try:
                await self.channel_layer.group_send(
                    g,
                    {
                        "type": "dispatch_event",
                        "app": "conversation",
                        "event": "user_online_status",
                        "data": {
                            "dialogue_slug": g.split("_", 1)[1],
                            "user_id": self.user.id,
                            "is_online": False,
                        },
                    },
                )
            except Exception:
                pass

        # Last seen broadcast (only when fully offline)
        try:
            ts = await get_last_seen(self.user.id)
            if not ts:
                ts = int(time.time())
                redis = await get_redis_connection()
                await redis.set(f"last_seen:{self.user.id}", ts)
                await redis.close()

            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            iso = dt.isoformat()
            disp = timesince(dt)

            for g in groups:
                try:
                    await self.channel_layer.group_send(
                        g,
                        {
                            "type": "dispatch_event",
                            "app": "conversation",
                            "event": "user_last_seen",
                            "data": {
                                "dialogue_slug": g.split("_", 1)[1],
                                "user_id": self.user.id,
                                "is_online": False,
                                "last_seen_epoch": ts,
                                "last_seen": iso,
                                "last_seen_display": disp,
                            },
                        },
                    )
                except Exception:
                    pass
        except Exception:
            pass


    # --------------------------------------------------------------
    # PING LOOP
    # --------------------------------------------------------------
    async def start_ping(self):
        try:
            while True:
                # Stop if connection closed
                if not self.connected:
                    return

                # Server ping → client pong (Central will refresh TTL)
                try:
                    await self.consumer.safe_send_json({
                        "type": "ping",
                        "timestamp": timezone.now().isoformat(),  # short trace
                    })
                except Exception:
                    return

                # Keep interval < Redis TTL (60s)
                try:
                    await asyncio.sleep(20)
                except asyncio.CancelledError:
                    return

        except asyncio.CancelledError:
            return



    # --------------------------------------------------------------
    def _disc_key(self):
        # Key by (user, device) so reconnect can cancel the pending cleanup
        return (self.user.id, self.device_id or "")

    # --------------------------------------------------------------
    # INTERNAL DISPATCHER (dict-based)
    # --------------------------------------------------------------
    async def _dispatch_incoming(self, data: dict):
        """
        Core router for all incoming events.
        - Called by:
          - receive() after json.loads
          - handle() from Central consumer (already dict)
          - handle_backend_event() for backend events
        """
        try:
            t = data.get("type")

            # Routing
            if t == "pong":
                try:
                    await refresh_user_connection(self.user.id, self.channel_name)
                except Exception as e:
                    logger.error(f"[Redis] refresh_user_connection failed: {e}")
                return
            if t == "upload_canceled":
                await self.handle_upload_canceled(data)
                return
            if t == "edit_message":
                await self.handle_edit_message(data)
                return
            if t == "typing_status":
                await self.handle_typing_status(data)
                return
            if t == "chat_message":
                await self.handle_message(data)
                return
            if t == "file_message":
                await self.handle_file_message(data)
                return
            if t == "file_upload_status":
                await self.handle_file_upload_status(data)
                return
            if t == "recording_status":
                await self.handle_recording_status(data)
                return
            if t == "soft_delete_message":
                await self.handle_soft_delete_message(data)
                return
            if t == "hard_delete_message":
                await self.handle_hard_delete_message(data)
                return
            if t == "mark_as_read":
                await self.mark_message_as_read(data)
                return
            if t == "mark_as_delivered":
                await self.handle_mark_as_delivered(data)
                return
            if t == "request_online_status":
                await self.handle_request_online_status(data.get("dialogue_slug"))
                return

        except Exception as e:
            await self.consumer.safe_send_json({"type": "error", "message": str(e)})


    # -----------------------------------------------------------
    # CENTRAL WS → ROUTER ENTRY POINT (already dict)
    # -----------------------------------------------------------
    async def handle(self, data):
        # data is already a dict from CentralWebSocketConsumer
        await self._dispatch_incoming(data)


    # -----------------------------------------------------------
    # CONNECT WRAPPER
    # -----------------------------------------------------------
    async def on_connect(self):
        await self.connect()


    # -----------------------------------------------------------
    # BACKEND EVENT DISPATCHER
    # -----------------------------------------------------------
    async def handle_backend_event(self, payload: dict):
        """
        Called ONLY from CentralWebSocketConsumer.dispatch_event.

        payload شکلش این است:
        {
            "event": "chat_message" | "mark_as_read" | "mark_as_delivered"
                      | "unread_count_update" | "user_online_status"
                      | "user_last_seen" | "typing_status_broadcast" | ...,
            "data": {...}
        }
        """
        event_type = payload.get("event")
        data = payload.get("data", {}) or {}

        # ---- Map backend event names to ws_* helpers ----
        if event_type == "chat_message":
            await self.ws_chat_message(data)

        elif event_type == "edit_message":
            await self.ws_edit_message(data)

        elif event_type == "file_message":
            await self.ws_file_message(data)

        elif event_type == "file_upload_status":
            await self.ws_file_upload_status(data)

        elif event_type == "upload_canceled":
            await self.ws_upload_canceled(data)

        elif event_type == "recording_status":
            await self.ws_recording_status(data)

        elif event_type in ("soft_delete_message", "message_soft_deleted"):
            await self.ws_soft_delete_message(data)

        elif event_type in ("hard_delete_message", "message_hard_deleted"):
            await self.ws_hard_delete_message(data)

        elif event_type == "mark_as_read":
            await self.ws_mark_as_read(data)

        elif event_type == "mark_as_delivered":
            await self.ws_mark_as_delivered(data)

        elif event_type in ("typing_status", "typing_status_broadcast"):
            await self.ws_typing_status(data)

        elif event_type == "unread_count_update":
            await self.ws_unread_count_update(data)

        elif event_type == "trigger_unread_count_update":
            await self.ws_trigger_unread_count_update(data)

        elif event_type == "user_online_status":
            await self.ws_user_online_status(data)

        elif event_type == "user_last_seen":
            await self.ws_user_last_seen(data)

        elif event_type == "force_logout":
            # Close this device socket immediately
            await self.force_logout(data)


        else:
            logger.warning(f"[ConversationHandler] Unknown backend event: {event_type}")



    # -----------------------------------------------------------
    # WS HELPERS: backend → frontend (JSON envelope)
    # -----------------------------------------------------------
    async def _send_conv_event(self, event_type: str, data: dict):
        await self.consumer.safe_send_json({
            "type": "event",
            "app": "conversation",
            "event": event_type,
            "data": data,
        })


    async def ws_chat_message(self, data: dict):
        await self._send_conv_event("chat_message", data)

    async def ws_mark_as_read(self, data: dict):
        await self._send_conv_event("mark_as_read", data)

    async def ws_mark_as_delivered(self, data: dict):
        await self._send_conv_event("mark_as_delivered", data)

    async def ws_unread_count_update(self, data: dict):
        await self._send_conv_event("unread_count_update", data)

    async def ws_user_online_status(self, data: dict):
        await self._send_conv_event("user_online_status", data)

    async def ws_user_last_seen(self, data: dict):
        await self._send_conv_event("user_last_seen", data)

    async def ws_typing_status(self, data: dict):
        await self._send_conv_event("typing_status", data)

    async def ws_edit_message(self, data):
        await self._send_conv_event("edit_message", data)

    async def ws_file_message(self, data):
        await self._send_conv_event("file_message", data)

    async def ws_file_upload_status(self, data):
        await self._send_conv_event("file_upload_status", data)

    async def ws_upload_canceled(self, data):
        await self._send_conv_event("upload_canceled", data)

    async def ws_recording_status(self, data):
        await self._send_conv_event("recording_status", data)

    async def ws_soft_delete_message(self, data):
        await self._send_conv_event("message_soft_deleted", data)

    async def ws_hard_delete_message(self, data):
        await self._send_conv_event("message_hard_deleted", data)

    async def ws_trigger_unread_count_update(self, data):
        await self._send_conv_event("trigger_unread_count_update", data)
