# # apps/conversation/consumers.py
# # ================================================================
# # Final Clean Architecture — Dialogue WebSocket Consumer
# # ================================================================
# import asyncio
# import json
# import time
# import logging
# from datetime import datetime
# from urllib.parse import parse_qs

# from channels.generic.websocket import AsyncJsonWebsocketConsumer
# from asgiref.sync import sync_to_async
# from channels.db import database_sync_to_async
# from django.utils import timezone
# from django.utils.timesince import timesince
# from django.contrib.auth import get_user_model

# from apps.accounts.models import UserDeviceKey
# from apps.conversation.models import Dialogue
# from apps.conversation.utils import get_message_content
# from apps.accounts.services.sender_verification import is_sender_device_verified
# from services.redis_online_manager import (
#     set_user_online,
#     set_user_offline,
#     refresh_user_connection,
#     get_online_status_for_users,
#     get_last_seen,
#     get_redis_connection,
# )

# # ---- Mixins ----------------------------------------------------
# from apps.conversation.realtime.mixins.presence import PresenceMixin, DISCONNECT_TIMERS
# from apps.conversation.realtime.mixins.typing import TypingMixin, TYPING_TIMEOUTS
# from apps.conversation.realtime.mixins.delivery import DeliveryMixin
# from apps.conversation.realtime.mixins.files import FileEventsMixin
# from apps.conversation.realtime.mixins.edits import EditDeleteMixin
# from apps.conversation.realtime.mixins.message import MessageMixin
# from apps.conversation.realtime.mixins.read import ReadMixin
# from apps.conversation.realtime.mixins.group_events import ConversationGroupMixin

# logger = logging.getLogger(__name__)
# User = get_user_model()


# # =================================================================
# #   Dialogue Consumer
# # =================================================================
# class DialogueConsumer(
#     AsyncJsonWebsocketConsumer,
#     PresenceMixin,
#     TypingMixin,
#     DeliveryMixin,
#     FileEventsMixin,
#     EditDeleteMixin,
#     MessageMixin,
#     ReadMixin,
#     ConversationGroupMixin,
# ):

#     # --------------------------------------------------------------
#     # CONNECT
#     # --------------------------------------------------------------
#     async def connect(self):
#         self.connected = True
#         self.user = self.scope.get("user")
#         self.slug = self.scope["url_route"]["kwargs"].get("slug")

#         # Parse device_id
#         qs = parse_qs(self.scope.get("query_string", b"").decode())
#         device_id = (qs.get("device_id", [""])[0] or "").strip().lower()
#         self.device_id = device_id if device_id else None

#         # Authentication Guard
#         if not self.user or not self.user.is_authenticated or not self.device_id:
#             await self.close()
#             return

#         # Device verification
#         belongs = await database_sync_to_async(
#             UserDeviceKey.objects.filter(
#                 user=self.user, device_id=self.device_id, is_active=True
#             ).exists
#         )()
#         if not belongs:
#             await self.close(code=4403)
#             return

#         # Cancel pending disconnect timers
#         key = self._disc_key()
#         if DISCONNECT_TIMERS.get(key):
#             DISCONNECT_TIMERS[key].cancel()
#             del DISCONNECT_TIMERS[key]

#         # Set user online
#         await set_user_online(self.user.id, self.channel_name)

#         # Subscribe to user/device groups
#         await self.channel_layer.group_add(f"user_{self.user.id}", self.channel_name)
#         await self.channel_layer.group_add(f"device_{self.device_id}", self.channel_name)

#         # Load dialogues
#         if self.slug:
#             try:
#                 dialogue = await sync_to_async(Dialogue.objects.get)(
#                     slug=self.slug, participants=self.user
#                 )
#                 self.dialogue_map = {f"dialogue_{dialogue.slug}": dialogue.id}
#                 dialogues = [dialogue]
#             except Dialogue.DoesNotExist:
#                 await self.close()
#                 return
#         else:
#             dialogues = await sync_to_async(list)(
#                 Dialogue.objects.filter(participants=self.user)
#             )
#             self.dialogue_map = {f"dialogue_{d.slug}": d.id for d in dialogues}

#         # Join dialogue groups
#         self.group_names = set(self.dialogue_map.keys())
#         for group in self.group_names:
#             await self.channel_layer.group_add(group, self.channel_name)

#         await self.accept()

#         # Ping loop
#         self.ping_task = asyncio.create_task(self.start_ping())

#         # Presence updates
#         await self.notify_user_online()
#         await self.send_all_online_statuses()

#         # Notify connected user
#         await self.send_json({
#             "type": "user_online_status",
#             "event_type": "user_online_status",
#             "dialogue_slugs": [d.slug for d in dialogues],
#             "user_id": self.user.id,
#             "is_online": True,
#         })

#         # Send undelivered messages to user
#         await self._push_undelivered_messages(dialogues)

#         # Broadcast presence to dialogue groups
#         for group in self.group_names:
#             await self.channel_layer.group_send(
#                 group,
#                 {
#                     "type": "user_online_status",
#                     "event_type": "user_online_status",
#                     "dialogue_slug": group.split("_", 1)[1],
#                     "user_id": self.user.id,
#                     "is_online": True,
#                 },
#             )

#     # --------------------------------------------------------------
#     # Push Undelivered Messages
#     # --------------------------------------------------------------
#     async def _push_undelivered_messages(self, dialogues):
#         for dialogue in dialogues:
#             undelivered = await sync_to_async(list)(
#                 dialogue.messages.filter(is_delivered=False).exclude(sender=self.user)
#             )

#             for msg in undelivered:
#                 try:
#                     await self.mark_message_as_delivered(msg)
#                     content = await database_sync_to_async(get_message_content)(msg, self.user)
#                     is_encrypted = await database_sync_to_async(
#                         lambda: msg.encryptions.exists()
#                     )()
#                 except Exception as e:
#                     logger.exception("Failed to push undelivered message: %s", e)
#                     continue

#                 await self.channel_layer.group_send(
#                     f"dialogue_{dialogue.slug}",
#                     {
#                         "type": "chat_message",
#                         "event_type": "chat_message",
#                         "message_id": msg.id,
#                         "dialogue_slug": dialogue.slug,
#                         "content": content,
#                         "sender": {
#                             "id": msg.sender.id,
#                             "username": msg.sender.username,
#                             "email": msg.sender.email,
#                         },
#                         "timestamp": msg.timestamp.isoformat(),
#                         "is_encrypted": is_encrypted,
#                         "is_delivered": True,
#                     },
#                 )

#                 await self.channel_layer.group_send(
#                     f"user_{msg.sender.id}",
#                     {
#                         "type": "mark_as_delivered",
#                         "event_type": "mark_as_delivered",
#                         "dialogue_slug": dialogue.slug,
#                         "message_id": msg.id,
#                         "user_id": self.user.id,
#                     },
#                 )

#     # --------------------------------------------------------------
#     # Force Logout
#     # --------------------------------------------------------------
#     async def force_logout(self, event):
#         if event["user_id"] == self.user.id:
#             self.force_logout_triggered = True
#             await self.finalize_disconnect()
#             await self.close()

#     # --------------------------------------------------------------
#     # DISCONNECT
#     # --------------------------------------------------------------
#     async def disconnect(self, close_code):
#         self.connected = False

#         # Stop ping task
#         if hasattr(self, "ping_task"):
#             self.ping_task.cancel()
#             from contextlib import suppress
#             with suppress(asyncio.CancelledError):
#                 await self.ping_task

#         # Forced-logout path
#         if getattr(self, "force_logout_triggered", False):
#             await self.finalize_disconnect()
#             return

#         # Per-connection disconnect timer
#         key = self._disc_key()

#         if DISCONNECT_TIMERS.get(key):
#             DISCONNECT_TIMERS[key].cancel()
#             del DISCONNECT_TIMERS[key]

#         async def delayed():
#             await asyncio.sleep(10)
#             if not getattr(self, "connected", False):
#                 await self.finalize_disconnect()

#         DISCONNECT_TIMERS[key] = asyncio.create_task(delayed())

#     # --------------------------------------------------------------
#     # FINALIZE DISCONNECT
#     # --------------------------------------------------------------
#     async def finalize_disconnect(self):
#         if getattr(self, "_finalized", False):
#             return
#         self._finalized = True
#         self.connected = False

#         # Stop ping
#         if hasattr(self, "ping_task"):
#             self.ping_task.cancel()
#             try: await self.ping_task
#             except asyncio.CancelledError: pass

#         # Mark offline
#         await set_user_offline(self.user.id, self.channel_name)

#         # Snapshot groups
#         groups = list(getattr(self, "group_names", []))

#         # Leave groups
#         for g in groups:
#             await self.channel_layer.group_discard(g, self.channel_name)
#         await self.channel_layer.group_discard(f"user_{self.user.id}", self.channel_name)
#         if getattr(self, "device_id", None):
#             await self.channel_layer.group_discard(f"device_{self.device_id}", self.channel_name)

#         # Notify offline
#         for g in groups:
#             await self.channel_layer.group_send(
#                 g,
#                 {
#                     "type": "user_online_status",
#                     "dialogue_slug": g.split("_", 1)[1],
#                     "user_id": self.user.id,
#                     "is_online": False,
#                 },
#             )

#         # Cleanup typing
#         if TYPING_TIMEOUTS.get(self.user.id):
#             TYPING_TIMEOUTS[self.user.id].cancel()
#             del TYPING_TIMEOUTS[self.user.id]

#         # Cleanup disconnect timer
#         key = self._disc_key()
#         if DISCONNECT_TIMERS.get(key):
#             DISCONNECT_TIMERS[key].cancel()
#             del DISCONNECT_TIMERS[key]

#         # Last seen broadcast
#         try:
#             statuses = await get_online_status_for_users([self.user.id])
#             fully_offline = not bool(statuses.get(self.user.id, False))

#             if fully_offline:
#                 ts = await get_last_seen(self.user.id)
#                 if not ts:
#                     ts = int(time.time())
#                     redis = await get_redis_connection()
#                     await redis.set(f"last_seen:{self.user.id}", ts)
#                     await redis.close()

#                 iso = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
#                 disp = timesince(datetime.fromtimestamp(ts, tz=timezone.utc))

#                 for g in groups:
#                     await self.channel_layer.group_send(
#                         g,
#                         {
#                             "type": "user_last_seen",
#                             "dialogue_slug": g.split("_", 1)[1],
#                             "user_id": self.user.id,
#                             "is_online": False,
#                             "last_seen_epoch": ts,
#                             "last_seen": iso,
#                             "last_seen_display": disp,
#                         },
#                     )
#         except Exception:
#             pass

#     # --------------------------------------------------------------
#     # PING LOOP
#     # --------------------------------------------------------------
#     async def start_ping(self):
#         try:
#             while self.connected:
#                 try:
#                     s = await get_online_status_for_users([self.user.id])
#                     if s.get(self.user.id, False):
#                         await self.send_json({
#                             "type": "ping",
#                             "timestamp": datetime.now().isoformat()
#                         })
#                 except Exception:
#                     break

#                 await asyncio.sleep(30)
#         except asyncio.CancelledError:
#             pass
#         except Exception as e:
#             logger.error("[start_ping] error: %s", e)

#     # --------------------------------------------------------------
#     def _disc_key(self):
#         return (self.user.id, self.channel_name)

#     # --------------------------------------------------------------
#     # RECEIVE DISPATCHER
#     # --------------------------------------------------------------
#     async def receive(self, text_data):
#         try:
#             data = json.loads(text_data)

#             t = data.get("type")

#             # Routing
#             if t == "pong":
#                 await refresh_user_connection(self.user.id, self.channel_name)
#                 return
#             if t == "upload_canceled":
#                 await self.handle_upload_canceled(data)
#                 return
#             if t == "edit_message":
#                 await self.handle_edit_message(data)
#                 return
#             if "is_typing" in data:
#                 await self.handle_typing_status(data)
#                 return
#             if t == "chat_message":
#                 await self.handle_message(data)
#                 return
#             if t == "file_message":
#                 await self.handle_file_message(data)
#                 return
#             if t == "file_upload_status":
#                 await self.handle_file_upload_status(data)
#                 return
#             if t == "recording_status":
#                 await self.handle_recording_status(data)
#                 return
#             if t == "soft_delete_message":
#                 await self.handle_soft_delete_message(data)
#                 return
#             if t == "hard_delete_message":
#                 await self.handle_hard_delete_message(data)
#                 return
#             if t == "mark_as_read":
#                 await self.mark_message_as_read(data)
#                 return
#             if t == "mark_as_delivered":
#                 await self.handle_mark_as_delivered(data)
#                 return
#             if t == "request_online_status":
#                 await self.handle_request_online_status(data.get("dialogue_slug"))
#                 return

#         except Exception as e:
#             await self.send_json({"type": "error", "message": str(e)})

