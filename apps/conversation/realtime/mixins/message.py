# apps/conversation/realtime/mixins/message.py
import base64
from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from django.utils import timezone

from apps.conversation.models import Message, Dialogue, MessageEncryption
from apps.accounts.services.sender_verification import is_sender_device_verified
from services.redis_online_manager import get_online_status_for_users
from apps.conversation.tasks import deliver_offline_message


class MessageMixin:
    """
    FULL Message Handling:
    - validate DM/Group rules
    - PoP sender verification
    - create message or encrypted envelopes
    - update last_message
    - self-destruct hook
    - broadcast (group or DM per-device)
    - delivery bookkeeping
    """

    # ---------------------------------------------
    # Entry point (called from consumer.receive)
    # ---------------------------------------------
    async def handle_message(self, data):
        dialogue_slug = (data.get("dialogue_slug") or "").strip()
        is_encrypted = bool(data.get("is_encrypted", False))
        encrypted_contents = data.get("encrypted_contents", [])

        if not dialogue_slug:
            await self.send_json({"type": "error", "code": "BAD_REQUEST",
                                  "message": "dialogue_slug is required"})
            return

        try:
            dialogue = await sync_to_async(Dialogue.objects.get)(
                slug=dialogue_slug, participants=self.user
            )
        except Dialogue.DoesNotExist:
            await self.send_json({"type": "error", "code": "NOT_FOUND",
                                  "message": "Dialogue not found"})
            return

        is_group = bool(dialogue.is_group)

        # --------------------------
        # Device PoP verification
        # --------------------------
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

        # --------------------------
        # Policy Validation
        # --------------------------
        if is_group and is_encrypted:
            await self.send_json({"type": "error", "code": "BAD_REQUEST",
                                  "message": "Group messages must not be encrypted"})
            return

        if (not is_group) and (not is_encrypted):
            await self.send_json({"type": "error", "code": "BAD_REQUEST",
                                  "message": "DM messages must be encrypted"})
            return

        # --------------------------
        # Create Message
        # --------------------------
        try:
            if is_group:
                # Plain-text for groups
                message = await self._create_group_message(dialogue, encrypted_contents)
            else:
                # E2EE per-device envelopes for DMs
                message = await self._create_dm_message(dialogue, encrypted_contents)

            # update last_message
            dialogue.last_message = message
            await sync_to_async(dialogue.save)(update_fields=["last_message"])

        except Exception as e:
            await self.send_json({"type": "error", "message": "Failed to save message",
                                  "details": str(e)})
            return

        # Self-destruct hook (unchanged)
        await self.handle_self_destruct_messages()

        # --------------------------
        # Broadcast
        # --------------------------
        participants = await sync_to_async(list)(dialogue.participants.all())
        user_ids = [p.id for p in participants if p.id != self.user.id]
        online_statuses = await get_online_status_for_users(user_ids)

        if is_group:
            await self._broadcast_group_message(dialogue, message, participants, online_statuses)
        else:
            await self._broadcast_dm_message(dialogue, message, participants, online_statuses)

    # ==========================================================
    # GROUP MESSAGE CREATION
    # ==========================================================
    async def _create_group_message(self, dialogue, encrypted_contents):
        plain_message = (
            encrypted_contents[0].get("encrypted_content")
            if encrypted_contents and isinstance(encrypted_contents, list)
            else ""
        ) or ""

        plain_message = plain_message.strip()
        if not plain_message:
            raise ValueError("Empty content")

        base64_str = base64.b64encode(plain_message.encode("utf-8")).decode("utf-8")
        content_bytes = base64_str.encode("utf-8")

        return await sync_to_async(Message.objects.create)(
            dialogue=dialogue,
            sender=self.user,
            content_encrypted=content_bytes,
        )

    # ==========================================================
    # DM MESSAGE CREATION (E2EE)
    # ==========================================================
    async def _create_dm_message(self, dialogue, encrypted_contents):
        if not isinstance(encrypted_contents, list) or not encrypted_contents:
            raise ValueError("encrypted_contents required for DM")

        # sanitize/dedupe by device_id
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
            raise ValueError("No valid encrypted contents")

        message = await sync_to_async(Message.objects.create)(
            dialogue=dialogue,
            sender=self.user,
            content_encrypted=b"[Encrypted]",
        )

        MAX_PER_MESSAGE = 500
        to_create = [
            MessageEncryption(
                message=message,
                device_id=it["device_id"],
                encrypted_content=it["encrypted_content"]
            )
            for it in clean_items[:MAX_PER_MESSAGE]
        ]
        await sync_to_async(MessageEncryption.objects.bulk_create)(to_create)

        return message

    # ==========================================================
    # BROADCASTING — GROUP
    # ==========================================================
    async def _broadcast_group_message(self, dialogue, message, participants, online):
        """Broadcast plaintext group message to all participants."""

        # decode plaintext
        plain_message = base64.b64decode(message.content_encrypted).decode("utf-8")

        # base immutable payload
        base_payload = {
            "message_id": message.id,
            "dialogue_slug": dialogue.slug,
            "content": plain_message,
            "sender": self._sender_obj(message),
            "timestamp": message.timestamp.isoformat(),
            "is_encrypted": False,
            "encrypted_for_device": None,
        }

        for participant in participants:
            # skip sender self-echo if you prefer (optional)
            # if participant.id == self.user.id:
            #     continue

            delivered = online.get(participant.id, False)

            # --- build safe per-user payload (avoid mutation bug) ---
            payload = dict(base_payload)
            payload["is_delivered"] = delivered

            # 🔥 send unified WS event
            await self.channel_layer.group_send(
                f"user_{participant.id}",
                {
                    "type": "dispatch_event",      # must match CentralConsumer
                    "app": "conversation",
                    "event": "chat_message",
                    "data": payload,
                },
            )

            # --- delivery bookkeeping ---
            if delivered:
                await self.mark_message_as_delivered(message)
            else:
                deliver_offline_message.delay(message.id)

            # --- unread counter event (consistent format) ---
            await self.channel_layer.group_send(
                f"user_{participant.id}",
                {
                    "type": "dispatch_event",
                    "app": "conversation",
                    "event": "unread_count_update",
                    "data": {
                        "payload": [
                            {
                                "dialogue_slug": dialogue.slug,
                                "unread_count": 1,
                                "sender_id": message.sender.id,
                            }
                        ]
                    },
                },
            )


    # ==========================================================
    # BROADCASTING — DM (PER DEVICE)
    # ==========================================================
    async def _broadcast_dm_message(self, dialogue, message, participants, online):
        """Broadcast E2EE encrypted DM message to each device."""

        enc_rows = await sync_to_async(list)(
            MessageEncryption.objects.filter(message=message)
            .values("device_id", "encrypted_content")
        )

        # per-device encrypted delivery
        for enc in enc_rows:
            device_id = enc["device_id"]
            encrypted_blob = enc["encrypted_content"]

            # immutable base payload
            payload = {
                "message_id": message.id,
                "dialogue_slug": dialogue.slug,
                "content": encrypted_blob,
                "sender": self._sender_obj(message),
                "timestamp": message.timestamp.isoformat(),
                "is_encrypted": True,
                "encrypted_for_device": device_id,
                "is_delivered": False,        # will update per user below
            }

            # 🔥 send to correct device group
            await self.channel_layer.group_send(
                f"device_{device_id}",
                {
                    "type": "dispatch_event",
                    "app": "conversation",
                    "event": "chat_message",
                    "data": payload,
                },
            )

        # per-user delivery + unread update
        for participant in participants:
            delivered = online.get(participant.id, False)

            # update delivery status
            if delivered:
                await self.mark_message_as_delivered(message)
            else:
                deliver_offline_message.delay(message.id)

            # unread counter update
            await self.channel_layer.group_send(
                f"user_{participant.id}",
                {
                    "type": "dispatch_event",
                    "app": "conversation",
                    "event": "unread_count_update",
                    "data": {
                        "payload": [
                            {
                                "dialogue_slug": dialogue.slug,
                                "unread_count": 1,
                                "sender_id": message.sender.id,
                            }
                        ]
                    },
                },
            )


    # ==========================================================
    # HELPER — sender object for frontend
    # ==========================================================
    def _sender_obj(self, message):
        return {
            "id": message.sender.id,
            "username": message.sender.username,
            "email": message.sender.email,
        }


    # ---------------------------------------------------
    # Self-destruct message handler
    # ---------------------------------------------------
    async def handle_self_destruct_messages(self):
        """
        Safely remove expired self-destruct messages.
        """
        try:
            messages_to_delete = await sync_to_async(
                lambda: Message.objects.filter(
                    sender=self.user,
                    self_destruct_at__lte=timezone.now()   # ✅ FIX
                )
            )()

            count = await sync_to_async(messages_to_delete.count)()
            if count > 0:
                await sync_to_async(messages_to_delete.delete)()

        except Exception as e:
            import logging
            logging.error(f"[SELF-DESTRUCT] Failed: {e}", exc_info=True)
