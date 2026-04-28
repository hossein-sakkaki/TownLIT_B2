# apps/conversation/realtime/handler.py

import logging

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model

from apps.conversation.models import Dialogue
from apps.conversation.utils import get_message_content
from apps.conversation.services.message_reply import build_reply_preview
from apps.conversation.services.message_forward import build_forward_preview

# ---- Mixins ----------------------------------------------------
from apps.conversation.realtime.mixins.typing import (
    TypingMixin,
    cancel_all_typing_timeouts_for_user,
)
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
# =================================================================
class ConversationHandler(
    MessageMixin,
    TypingMixin,
    DeliveryMixin,
    FileEventsMixin,
    EditDeleteMixin,
    ReadMixin,
    ConversationGroupMixin,
):
    """
    Conversation realtime handler.

    Responsibility:
    - receive canonical WS app messages
    - call conversation mixins
    - dispatch backend conversation events to client

    Notes:
    - Transport heartbeat/pong is owned by CentralWebSocketConsumer.
    - Core domain mutations are handled by services.
    - This handler coordinates conversation realtime behavior only.
    """

    APP = "conversation"

    def __init__(self, consumer):
        self.consumer = consumer

        # Forward essential fields
        self.user = consumer.user
        self.device_id = consumer.device_id
        self.scope = consumer.scope
        self.channel_layer = consumer.channel_layer
        self.channel_name = consumer.channel_name

        # Flags
        self.connected = False
        self._finalized = False
        self.force_logout_triggered = False

        # Dialogue state
        self.slug = None
        self.group_names = set()
        self.dialogue_map = {}
        self.user_device_group = None

    # --------------------------------------------------------------
    # Helpers
    # --------------------------------------------------------------
    def _message_data(self, message: dict) -> dict:
        """
        Canonical app payload accessor.
        """
        data = message.get("data")
        if isinstance(data, dict):
            return data
        return {}

    async def _send_error(self, code: str, message: str, details: dict | None = None):
        """
        Send canonical conversation app error.
        """
        await self.consumer.send_app_error(
            app=self.APP,
            code=code,
            message=message,
            details=details,
        )

    async def _send_conv_event(self, event_type: str, data: dict):
        await self.consumer.send_app_event(
            app=self.APP,
            event=event_type,
            data=data,
        )

    async def _build_replay_payload(self, msg, dialogue):
        """
        Build enriched replay payload for undelivered messages.

        Includes:
        - delivery metadata
        - reply metadata
        - forward metadata
        - safe DM/group content handling
        """
        has_encryptions = await database_sync_to_async(
            lambda: msg.encryptions.exists()
        )()

        reply_preview = await database_sync_to_async(build_reply_preview)(
            message=msg,
            acting_user=self.user,
        )
        forward_preview = await database_sync_to_async(build_forward_preview)(
            message=msg,
        )

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
            "reply_to_message_id": getattr(msg, "reply_to_id", None),
            "reply_preview": reply_preview,
            "is_forwarded": bool(getattr(msg, "is_forwarded", False)),
            "forwarded_from_message_id": getattr(msg, "forwarded_from_id", None),
            "forward_preview": forward_preview,
        }

        if has_encryptions:
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
            content = await database_sync_to_async(get_message_content)(
                msg,
                self.user,
            )

            payload.update({
                "is_encrypted": False,
                "decrypted_content": content,
                "content": None,
                "encrypted_for_device": None,
            })

        return payload

    # --------------------------------------------------------------
    # Connect
    # --------------------------------------------------------------
    async def connect(self):
        self.user = self.consumer.user
        self.device_id = self.consumer.device_id
        self.connected = True

        self.slug = self.scope.get("url_route", {}).get("kwargs", {}).get("slug")

        if not self.user or not self.user.is_authenticated:
            await self.consumer.close()
            return

        dialogues = await sync_to_async(list)(
            Dialogue.objects.filter(participants=self.user)
        )

        dialogue_slugs = {d.slug for d in dialogues}
        if self.slug and self.slug not in dialogue_slugs:
            await self.consumer.close()
            return

        self.dialogue_map = {f"dialogue_{d.slug}": d.id for d in dialogues}
        self.group_names = set(self.dialogue_map.keys())

        # Join dialogue groups
        for group_name in self.group_names:
            try:
                await self.consumer.join_feature_group(group_name)
            except Exception as e:
                logger.error(f"[Conversation] group join failed ({group_name}): {e}")

        # Join user-device scoped group for secure DM delivery
        if self.device_id:
            self.user_device_group = f"user_device_{self.user.id}_{self.device_id}"
            try:
                await self.consumer.join_feature_group(self.user_device_group)
            except Exception as e:
                logger.error(
                    f"[Conversation] user_device group join failed ({self.user_device_group}): {e}"
                )

        # Replay undelivered messages
        await self._push_undelivered_messages(dialogues)

        # IMPORTANT:
        # After reconnect/login, client state is empty.
        # Push authoritative unread snapshot so badges are restored correctly.
        await self.send_unread_counts()

    # --------------------------------------------------------------
    # Disconnect
    # --------------------------------------------------------------
    async def on_connect(self):
        await self.connect()

    async def on_disconnect(self):
        await self.disconnect(1000)

    async def disconnect(self, close_code):
        self.connected = False
        await self.finalize_disconnect()

    async def finalize_disconnect(self):
        if getattr(self, "_finalized", False):
            return

        self._finalized = True
        self.connected = False

        # Group cleanup is owned by CentralWebSocketConsumer.feature_groups
        # Keep only conversation-local cleanup here.
        if getattr(self, "user", None) and not self.user.is_anonymous:
            cancel_all_typing_timeouts_for_user(self.user.id)

    # --------------------------------------------------------------
    # Push undelivered messages
    # --------------------------------------------------------------
    async def _push_undelivered_messages(self, dialogues):
        for dialogue in dialogues:
            undelivered = await sync_to_async(list)(
                dialogue.messages
                .select_related("sender", "reply_to", "forwarded_from")
                .filter(is_delivered=False)
                .exclude(sender=self.user)
                .exclude(deleted_by_users=self.user)
            )

            for msg in undelivered:
                try:
                    await self.mark_message_as_delivered(msg)
                    payload = await self._build_replay_payload(msg, dialogue)

                except Exception as e:
                    logger.exception("Failed to push undelivered message: %s", e)
                    continue

                if dialogue.is_group:
                    await self.channel_layer.group_send(
                        f"dialogue_{dialogue.slug}",
                        {
                            "type": "dispatch_event",
                            "app": "conversation",
                            "event": "chat_message",
                            "data": payload,
                        },
                    )
                else:
                    if self.device_id:
                        await self.channel_layer.group_send(
                            f"user_device_{self.user.id}_{self.device_id}",
                            {
                                "type": "dispatch_event",
                                "app": "conversation",
                                "event": "chat_message",
                                "data": payload,
                            },
                        )

    # --------------------------------------------------------------
    # Force logout
    # --------------------------------------------------------------
    async def force_logout(self, event):
        if int(event.get("user_id") or 0) == self.user.id:
            self.force_logout_triggered = True
            await self.finalize_disconnect()
            await self.consumer.close()

    # --------------------------------------------------------------
    # Internal dispatcher
    # --------------------------------------------------------------
    async def _dispatch_incoming(self, message: dict):
        """
        Route canonical conversation command messages.

        Canonical incoming shape from central consumer:
            {
                "app": "conversation",
                "type": "...",
                "data": {...}
            }
        """
        try:
            msg_type = message.get("type")
            data = self._message_data(message)

            if msg_type == "upload_canceled":
                await self.handle_upload_canceled(data)
                return

            if msg_type == "edit_message":
                await self.handle_edit_message(data)
                return

            if msg_type == "typing_status":
                await self.handle_typing_status(data)
                return

            if msg_type == "chat_message":
                await self.handle_message(data)
                return

            if msg_type == "file_message":
                await self.handle_file_message(data)
                return

            if msg_type == "file_upload_status":
                await self.handle_file_upload_status(data)
                return

            if msg_type == "recording_status":
                await self.handle_recording_status(data)
                return

            if msg_type == "soft_delete_message":
                await self.handle_soft_delete_message(data)
                return

            if msg_type == "hard_delete_message":
                await self.handle_hard_delete_message(data)
                return

            if msg_type == "mark_as_read":
                await self.mark_message_as_read(data)
                return

            if msg_type == "mark_as_delivered":
                await self.handle_mark_as_delivered(data)
                return

            await self._send_error(
                code="UNKNOWN_COMMAND",
                message=f"Unknown conversation command '{msg_type}'",
            )

        except Exception as e:
            logger.exception("[ConversationHandler] dispatch failed: %s", e)
            await self._send_error(
                code="CONVERSATION_DISPATCH_FAILED",
                message="Conversation command dispatch failed",
            )

    # -----------------------------------------------------------
    # Central WS entry
    # -----------------------------------------------------------
    async def handle(self, message):
        await self._dispatch_incoming(message)

    # -----------------------------------------------------------
    # Backend event dispatcher
    # -----------------------------------------------------------
    async def handle_backend_event(self, payload: dict):
        event_type = payload.get("event")
        data = payload.get("data", {}) or {}

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
        elif event_type == "message_soft_deleted":
            await self.ws_soft_delete_message(data)
        elif event_type == "message_hard_deleted":
            await self.ws_hard_delete_message(data)
        elif event_type == "typing_status":
            await self.ws_typing_status(data)
        elif event_type == "mark_as_read":
            await self.ws_mark_as_read(data)
        elif event_type == "mark_as_delivered":
            await self.ws_mark_as_delivered(data)
        elif event_type == "unread_count_update":
            await self.ws_unread_count_update(data)
        elif event_type == "trigger_unread_count_update":
            await self.ws_trigger_unread_count_update(data)
        elif event_type == "dialogue_pinned":
            await self.ws_dialogue_pinned(data)
        elif event_type == "dialogue_unpinned":
            await self.ws_dialogue_unpinned(data)
        elif event_type == "message_pinned":
            await self.ws_message_pinned(data)
        elif event_type == "message_unpinned":
            await self.ws_message_unpinned(data)
        elif event_type == "message_reaction_toggled":
            await self.ws_message_reaction_toggled(data)
        elif event_type == "message_reaction_summary":
            await self.ws_message_reaction_summary(data)
        elif event_type == "group_added":
            await self.group_added(data)
        elif event_type == "group_removed":
            await self.group_removed(data)
        elif event_type == "group_left":
            await self.group_left(data)
        elif event_type == "founder_transferred":
            await self.founder_transferred(data)
        elif event_type == "force_logout":
            await self.force_logout(data)
        else:
            logger.warning(f"[ConversationHandler] Unknown backend event: {event_type}")

    # -----------------------------------------------------------
    # WS event forwarding helpers
    # -----------------------------------------------------------
    async def ws_chat_message(self, data: dict):
        await self._send_conv_event("chat_message", data)

    async def ws_mark_as_read(self, data: dict):
        await self._send_conv_event("mark_as_read", data)

    async def ws_mark_as_delivered(self, data: dict):
        await self._send_conv_event("mark_as_delivered", data)

    async def ws_unread_count_update(self, data: dict):
        await self._send_conv_event("unread_count_update", data)

    async def ws_typing_status(self, data: dict):
        await self._send_conv_event("typing_status", data)

    async def ws_edit_message(self, data: dict):
        await self._send_conv_event("edit_message", data)

    async def ws_file_message(self, data: dict):
        await self._send_conv_event("file_message", data)

    async def ws_file_upload_status(self, data: dict):
        await self._send_conv_event("file_upload_status", data)

    async def ws_upload_canceled(self, data: dict):
        await self._send_conv_event("upload_canceled", data)

    async def ws_recording_status(self, data: dict):
        await self._send_conv_event("recording_status", data)

    async def ws_soft_delete_message(self, data: dict):
        await self._send_conv_event("message_soft_deleted", data)

    async def ws_hard_delete_message(self, data: dict):
        await self._send_conv_event("message_hard_deleted", data)

    async def ws_trigger_unread_count_update(self, data: dict):
        await self._send_conv_event("trigger_unread_count_update", data)

    async def ws_dialogue_pinned(self, data: dict):
        await self._send_conv_event("dialogue_pinned", data)

    async def ws_dialogue_unpinned(self, data: dict):
        await self._send_conv_event("dialogue_unpinned", data)

    async def ws_message_pinned(self, data: dict):
        await self._send_conv_event("message_pinned", data)

    async def ws_message_unpinned(self, data: dict):
        await self._send_conv_event("message_unpinned", data)

    async def ws_message_reaction_toggled(self, data: dict):
        await self._send_conv_event("message_reaction_toggled", data)

    async def ws_message_reaction_summary(self, data: dict):
        await self._send_conv_event("message_reaction_summary", data)