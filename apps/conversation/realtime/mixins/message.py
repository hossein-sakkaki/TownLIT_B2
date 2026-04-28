# apps/conversation/realtime/mixins/message.py

import base64

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from django.utils import timezone

from apps.conversation.models import Message, Dialogue, MessageEncryption
from apps.accounts.models.devices import UserDeviceKey
from apps.accounts.services.sender_verification import is_sender_device_verified
from apps.core.websocket.services.redis_online_manager import get_online_status_for_users
from apps.conversation.tasks import deliver_offline_message
from apps.conversation.services.message_creation import create_text_message
from apps.conversation.services.event_contracts import (
    build_dm_chat_message_data,
    build_group_chat_message_data,
    build_unread_incremental_event_data,
)
from apps.conversation.services.message_reply import build_reply_preview
from apps.conversation.services.message_forward import build_forward_preview


class MessageMixin:
    """
    Full conversation message handling:
    - validate DM/Group rules
    - PoP sender verification
    - create message or encrypted envelopes
    - update last_message through service layer
    - self-destruct cleanup hook
    - broadcast group or DM message
    - delivery bookkeeping
    """

    # ------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------
    async def handle_message(self, data):
        dialogue_slug = (data.get("dialogue_slug") or "").strip()
        is_encrypted = bool(data.get("is_encrypted", False))
        content = (data.get("content") or "").strip()
        encrypted_contents = data.get("encrypted_contents", [])

        if not dialogue_slug:
            await self._send_error(
                code="BAD_REQUEST",
                message="dialogue_slug is required",
            )
            return

        try:
            dialogue = await sync_to_async(Dialogue.objects.get)(
                slug=dialogue_slug,
                participants=self.user,
            )
        except Dialogue.DoesNotExist:
            await self._send_error(
                code="NOT_FOUND",
                message="Dialogue not found",
            )
            return

        # Re-open dialogue on first outgoing message
        await database_sync_to_async(dialogue.release_inbound_block_on_outgoing)(self.user)

        recipient = None
        hidden_recipient_ids = set()

        if not dialogue.is_group:
            recipient = await sync_to_async(
                lambda: dialogue.participants.exclude(id=self.user.id).first()
            )()

            if recipient:
                should_restore = await database_sync_to_async(
                    dialogue.should_restore_on_incoming_for_user
                )(recipient)

                if should_restore:
                    await database_sync_to_async(dialogue.restore_dialogue)(recipient)

                should_hide = await database_sync_to_async(
                    dialogue.should_hide_incoming_for_user
                )(recipient)

                if should_hide:
                    hidden_recipient_ids.add(recipient.id)

        is_group = bool(dialogue.is_group)

        # Sender PoP
        verified = await database_sync_to_async(is_sender_device_verified)(
            self.user,
            self.device_id,
            dialogue_is_group=is_group,
        )
        if not verified:
            await self._send_error(
                code="SENDER_DEVICE_UNVERIFIED",
                message="Sender device is not verified",
            )
            return

        result = await database_sync_to_async(create_text_message)(
            dialogue=dialogue,
            sender=self.user,
            is_encrypted=is_encrypted,
            content=content,
            encrypted_contents=encrypted_contents,
            recipient_hidden_on_incoming=bool(hidden_recipient_ids),
            recipient=recipient,
        )

        if not result.get("ok"):
            await self._send_error(
                code=result.get("code", "MESSAGE_CREATE_FAILED"),
                message=result.get("message", "Failed to create message"),
            )
            return

        message = result["payload"]["message"]

        # Self-destruct cleanup hook
        await self.handle_self_destruct_messages()

        participants = await sync_to_async(list)(dialogue.participants.all())
        other_user_ids = [p.id for p in participants if p.id != self.user.id]
        online_statuses = await get_online_status_for_users(other_user_ids)

        if is_group:
            await self._broadcast_group_message(
                dialogue=dialogue,
                message=message,
                participants=participants,
                online=online_statuses,
            )
            return

        await self._broadcast_dm_message(
            dialogue=dialogue,
            message=message,
            participants=participants,
            online=online_statuses,
            hidden_recipient_ids=hidden_recipient_ids,
        )

    # ==========================================================
    # BROADCASTING — GROUP
    # ==========================================================
    async def _broadcast_group_message(self, dialogue, message, participants, online):
        """
        Broadcast plaintext group message to all participants, including sender.
        """
        plain_message = self._decode_group_plaintext(message)

        reply_preview = await database_sync_to_async(build_reply_preview)(
            message=message,
            acting_user=self.user,
        )
        forward_preview = await database_sync_to_async(build_forward_preview)(
            message=message,
        )

        base_payload = build_group_chat_message_data(
            message=message,
            plain_text=plain_message,
            reply_preview=reply_preview,
            forward_preview=forward_preview,
        )

        for participant in participants:
            payload = dict(base_payload)

            if participant.id == self.user.id:
                payload["is_delivered"] = False
            else:
                payload["is_delivered"] = bool(online.get(participant.id, False))

            await self.channel_layer.group_send(
                f"user_{participant.id}",
                {
                    "type": "dispatch_event",
                    "app": "conversation",
                    "event": "chat_message",
                    "data": payload,
                },
            )

        for participant in participants:
            if participant.id == self.user.id:
                continue

            await self._broadcast_incremental_unread_count(
                dialogue_slug=dialogue.slug,
                recipient_user_id=participant.id,
                sender_id=message.sender.id,
            )

    # ==========================================================
    # BROADCASTING — DM (PER DEVICE)
    # ==========================================================
    async def _broadcast_dm_message(
        self,
        dialogue,
        message,
        participants,
        online,
        hidden_recipient_ids=None,
    ):
        """
        Broadcast E2EE DM message to:
        - sender's own user-device groups
        - recipient's visible user-device groups
        """
        hidden_recipient_ids = hidden_recipient_ids or set()

        sender_id = self.user.id
        recipient_users = [p for p in participants if p.id != sender_id]

        user_device_map = {}
        participant_ids = [p.id for p in participants]

        reply_preview = await database_sync_to_async(build_reply_preview)(
            message=message,
            acting_user=self.user,
        )
        forward_preview = await database_sync_to_async(build_forward_preview)(
            message=message,
        )
        
        for uid in participant_ids:
            user_device_map[uid] = set(
                await sync_to_async(list)(
                    UserDeviceKey.objects.filter(user_id=uid, is_active=True)
                    .values_list("device_id", flat=True)
                )
            )

        enc_rows = await sync_to_async(list)(
            MessageEncryption.objects.filter(message=message)
            .values("device_id", "encrypted_content")
        )

        # Sender echo
        sender_device_ids = user_device_map.get(sender_id, set())

        for enc in enc_rows:
            device_id = enc["device_id"]
            encrypted_blob = enc["encrypted_content"]

            if device_id not in sender_device_ids:
                continue

            payload = build_dm_chat_message_data(
                message=message,
                encrypted_content=encrypted_blob,
                device_id=device_id,
                reply_preview=reply_preview,
                forward_preview=forward_preview,
            )
            payload["is_delivered"] = False

            await self.channel_layer.group_send(
                f"user_device_{sender_id}_{device_id}",
                {
                    "type": "dispatch_event",
                    "app": "conversation",
                    "event": "chat_message",
                    "data": payload,
                },
            )

        # Recipient visible devices
        for participant in recipient_users:
            if participant.id in hidden_recipient_ids:
                continue

            recipient_device_ids = user_device_map.get(participant.id, set())
            if not recipient_device_ids:
                continue

            for enc in enc_rows:
                device_id = enc["device_id"]
                encrypted_blob = enc["encrypted_content"]

                if device_id not in recipient_device_ids:
                    continue

                payload = build_dm_chat_message_data(
                    message=message,
                    encrypted_content=encrypted_blob,
                    device_id=device_id,
                    reply_preview=reply_preview,
                    forward_preview=forward_preview,
                )

                await self.channel_layer.group_send(
                    f"user_device_{participant.id}_{device_id}",
                    {
                        "type": "dispatch_event",
                        "app": "conversation",
                        "event": "chat_message",
                        "data": payload,
                    },
                )

        # Delivery + unread
        for participant in recipient_users:
            if participant.id in hidden_recipient_ids:
                continue

            delivered = bool(online.get(participant.id, False))

            if delivered:
                await self.mark_message_as_delivered(message)
            else:
                deliver_offline_message.delay(message.id)

            await self._broadcast_incremental_unread_count(
                dialogue_slug=dialogue.slug,
                recipient_user_id=participant.id,
                sender_id=message.sender.id,
            )

    # ==========================================================
    # HELPERS
    # ==========================================================
    def _decode_group_plaintext(self, message) -> str:
        """
        Decode stored group plaintext payload safely.
        """
        try:
            return base64.b64decode(message.content_encrypted).decode("utf-8")
        except Exception:
            return ""

    async def _broadcast_incremental_unread_count(
        self,
        dialogue_slug: str,
        recipient_user_id: int,
        sender_id: int,
    ):
        await self.channel_layer.group_send(
            f"user_{recipient_user_id}",
            {
                "type": "dispatch_event",
                "app": "conversation",
                "event": "unread_count_update",
                "data": build_unread_incremental_event_data(
                    dialogue_slug=dialogue_slug,
                    sender_id=sender_id,
                    unread_count=1,
                ),
            },
        )

    # ------------------------------------------------------------
    # Self-destruct cleanup
    # ------------------------------------------------------------
    async def handle_self_destruct_messages(self):
        """
        Safely remove expired self-destruct messages for current sender.
        """
        try:
            messages_to_delete = await sync_to_async(
                lambda: Message.objects.filter(
                    sender=self.user,
                    self_destruct_at__lte=timezone.now(),
                )
            )()

            count = await sync_to_async(messages_to_delete.count)()
            if count > 0:
                await sync_to_async(messages_to_delete.delete)()

        except Exception as e:
            import logging
            logging.error(f"[SELF-DESTRUCT] Failed: {e}", exc_info=True)