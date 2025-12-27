# apps/conversation/realtime/mixins/edits.py

import json
import base64
from django.utils import timezone
from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from django.db import transaction

from apps.conversation.models import Message, MessageEncryption, Dialogue
from apps.accounts.services.sender_verification import is_sender_device_verified

# ----------------------------------------------------------------

@database_sync_to_async
def reset_message_encryptions(message, clean_items):
    """
    Fully reset MessageEncryption rows for a message in 1 atomic block.
    Ensures no duplicate device_id rows remain.
    """

    with transaction.atomic():
        # Delete old rows
        MessageEncryption.objects.filter(message=message).delete()

        # Recreate new envelopes
        to_create = [
            MessageEncryption(
                message=message,
                device_id=item["device_id"],
                encrypted_content=item["encrypted_content"],
            )
            for item in clean_items
        ]

        if to_create:
            MessageEncryption.objects.bulk_create(to_create)

    # Return nothing (safe)


# ----------------------------------------------------------------
class EditDeleteMixin:
    """
    Handles:
    - Editing messages (group plaintext + DM encrypted envelopes)
    - Soft delete
    - Hard delete (rules: sender+unseen OR group admin)
    - Broadcasting all WS events identically to original consumer behavior
    """

    # ------------------------------------------------------------
    # EDIT MESSAGE
    # ------------------------------------------------------------
    async def handle_edit_message(self, data):
        message_id = data.get("message_id")
        is_encrypted = bool(data.get("is_encrypted", False))  # required so don't remove
        encrypted_contents = data.get("encrypted_contents", [])
        new_content = (data.get("new_content") or "").strip()

        if not message_id:
            return

        # Load message
        try:
            message = await sync_to_async(
                Message.objects.select_related("dialogue").get
            )(id=message_id)
        except Message.DoesNotExist:
            return

        # Sender-only rule
        if message.sender_id != self.user.id:
            return

        dialogue = message.dialogue
        dialogue_slug = dialogue.slug
        is_group = bool(dialogue.is_group)
        now = timezone.now()

        # PoP enforcement for DMs
        verified = await database_sync_to_async(is_sender_device_verified)(
            self.user, self.device_id, dialogue_is_group=is_group
        )
        if not verified:
            await self.consumer.safe_send_json({
                "type": "error",
                "code": "SENDER_DEVICE_UNVERIFIED",
                "message": "Sender device is not verified"
            })
            return

        # ----------------------------
        # GROUP EDIT (plaintext)
        # ----------------------------
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

        # ----------------------------
        # DM EDIT (encrypted contents)
        # ----------------------------
        else:
            if not isinstance(encrypted_contents, list) or not encrypted_contents:
                await self.consumer.safe_send_json({
                    "type": "error",
                    "code": "BAD_REQUEST",
                    "message": "encrypted_contents required for DM edit"
                })
                return

            # Sanitize + dedupe envelopes
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
                clean_items.append({
                    "device_id": dev,
                    "encrypted_content": enc
                })

            if not clean_items:
                await self.consumer.safe_send_json({
                    "type": "error",
                    "code": "BAD_REQUEST",
                    "message": "No valid encrypted contents"
                })
                return

            # Replace envelopes
            await reset_message_encryptions(message, clean_items)

            await sync_to_async(setattr)(message, "content_encrypted", b"[Encrypted]")
            await sync_to_async(setattr)(message, "is_edited", True)
            await sync_to_async(setattr)(message, "edited_at", now)
            await sync_to_async(message.save)()

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
                        "type": "dispatch_event",
                        "app": "conversation",
                        "event": "edit_message",
                        "data": {
                            "message_id": message.id,
                            "dialogue_slug": dialogue_slug,
                            "new_content": new_content,
                            "decrypted_content": new_content,
                            "edited_at": now.isoformat(),
                            "is_encrypted": False,
                            "is_edited": True,
                            "sender": {
                                "id": message.sender.id,
                                "username": message.sender.username,
                            },
                        }
                    }
                )

        else:
            enc_rows = await sync_to_async(list)(
                MessageEncryption.objects.filter(message=message)
                .values("device_id", "encrypted_content")
            )

            for enc in enc_rows:
                await self.channel_layer.group_send(
                    f"device_{enc['device_id']}",
                    {
                        "type": "dispatch_event",
                        "app": "conversation",
                        "event": "edit_message",
                        "data": {
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
                    }
                )


    # ------------------------------------------------------------
    # SOFT DELETE
    # ------------------------------------------------------------
    async def handle_soft_delete_message(self, data):
        message_id = data.get("message_id")
        user = self.user

        try:
            message = await sync_to_async(
                Message.objects.select_related("dialogue").get
            )(id=message_id)
        except Message.DoesNotExist:
            return

        # mark as soft deleted for this user
        await sync_to_async(lambda: message.mark_as_deleted_by_user(user))()

        dialogue_slug = message.dialogue.slug  # ✅ مهم

        # ✅ send unified event to THIS user group (all their connected devices)
        await self.channel_layer.group_send(
            f"user_{user.id}",
            {
                "type": "dispatch_event",
                "app": "conversation",
                "event": "message_soft_deleted",
                "data": {
                    "dialogue_slug": dialogue_slug,
                    "message_id": message.id,
                    "user_id": user.id,
                },
            },
        )

        # unread refresh (اگر فرانت handler دارد)
        await self.channel_layer.group_send(
            f"user_{user.id}",
            {
                "type": "dispatch_event",
                "app": "conversation",
                "event": "trigger_unread_count_update",
                "data": {},
            },
        )


    # ------------------------------------------------------------
    # HARD DELETE (Unified + Real-time)
    # ------------------------------------------------------------
    async def handle_hard_delete_message(self, data):
        message_id = data.get("message_id")
        user = self.user

        if not message_id:
            return

        # load message + dialogue
        try:
            message = await sync_to_async(
                Message.objects.select_related("dialogue", "sender").get
            )(id=message_id)
        except Message.DoesNotExist:
            return

        dialogue = message.dialogue
        dialogue_slug = dialogue.slug

        # authorization checks
        is_sender = (message.sender_id == user.id)
        is_unseen = await sync_to_async(lambda: message.seen_by_users.count() == 0)()
        is_group_admin = await sync_to_async(
            lambda: bool(dialogue.is_group) and dialogue.is_admin(user)
        )()

        # EXACT rule:
        if not ((is_sender and is_unseen) or is_group_admin):
            return

        # capture participants BEFORE deleting the message
        participants = await sync_to_async(list)(dialogue.participants.all())
        participant_ids = [p.id for p in participants]

        # --------------------------------------------------
        # delete assets + encryptions + DB row
        # --------------------------------------------------
        try:
            # delete file data if exists
            if message.image:
                await sync_to_async(message.image.delete)(save=False)
            if message.video:
                await sync_to_async(message.video.delete)(save=False)
            if message.audio:
                await sync_to_async(message.audio.delete)(save=False)
            if message.file:
                await sync_to_async(message.file.delete)(save=False)

            # remove encryptions
            await sync_to_async(lambda: message.encryptions.all().delete())()

            # delete message row
            await sync_to_async(message.delete)()

        except Exception as e:
            # never crash the socket loop; optional: send error back to requester
            await self.consumer.safe_send_json({
                "type": "error",
                "code": "HARD_DELETE_FAILED",
                "message": "Failed to hard delete message",
                "details": str(e),
            })
            return

        # --------------------------------------------------
        # broadcast hard delete event to ALL participants
        # --------------------------------------------------
        for uid in participant_ids:
            await self.channel_layer.group_send(
                f"user_{uid}",
                {
                    "type": "dispatch_event",
                    "app": "conversation",
                    "event": "message_hard_deleted",
                    "data": {
                        "dialogue_slug": dialogue_slug,
                        "message_id": message_id,
                    },
                },
            )

        # --------------------------------------------------
        # refresh unread counts for ALL participants
        # --------------------------------------------------
        for uid in participant_ids:
            await self.channel_layer.group_send(
                f"user_{uid}",
                {
                    "type": "dispatch_event",
                    "app": "conversation",
                    "event": "trigger_unread_count_update",
                    "data": {},
                },
            )
