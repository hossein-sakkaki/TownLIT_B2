# apps/conversation/realtime/mixins/edits.py

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from django.db import transaction

from apps.conversation.models import Message, MessageEncryption
from apps.accounts.models.devices import UserDeviceKey
from apps.accounts.services.sender_verification import is_sender_device_verified
from apps.conversation.services.message_mutations import (
    edit_message_content,
    hard_delete_message_for_user,
)
from apps.conversation.services.event_contracts import (
    build_dm_edit_message_data,
    build_group_edit_message_data,
    build_hard_delete_event_data,
    build_soft_delete_event_data,
)


@database_sync_to_async
def reset_message_encryptions(message, clean_items):
    """
    Fully reset MessageEncryption rows for a message in one atomic block.
    Ensures no duplicate device_id rows remain.
    """
    with transaction.atomic():
        MessageEncryption.objects.filter(message=message).delete()

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


class EditDeleteMixin:
    """
    Realtime edit/delete orchestration for conversation events.
    """

    # ------------------------------------------------------------
    # EDIT MESSAGE
    # ------------------------------------------------------------
    async def handle_edit_message(self, data):
        message_id = data.get("message_id")
        new_content = (data.get("new_content") or data.get("content") or "").strip()
        encrypted_contents = data.get("encrypted_contents", [])

        if not message_id:
            return

        try:
            message = await sync_to_async(
                Message.objects.select_related("dialogue", "sender").get
            )(id=message_id)
        except Message.DoesNotExist:
            await self._send_error(
                code="MESSAGE_NOT_FOUND",
                message="Message not found",
            )
            return

        dialogue = message.dialogue
        is_group = bool(dialogue.is_group)

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

        result = await database_sync_to_async(edit_message_content)(
            message_id=message_id,
            acting_user=self.user,
            new_content=new_content,
            encrypted_contents=encrypted_contents,
        )

        if not result.get("ok"):
            await self._send_error(
                code=result.get("code", "EDIT_FAILED"),
                message=result.get("message", "Failed to edit message"),
            )
            return

        payload = result["payload"]

        if payload["is_group"]:
            group_edit_data = build_group_edit_message_data(payload=payload)

            participants = await sync_to_async(list)(dialogue.participants.all())

            for participant in participants:
                await self.channel_layer.group_send(
                    f"user_{participant.id}",
                    {
                        "type": "dispatch_event",
                        "app": "conversation",
                        "event": "edit_message",
                        "data": group_edit_data,
                    },
                )
            return

        participants = await sync_to_async(list)(dialogue.participants.all())
        participant_ids = [p.id for p in participants]

        user_device_map = {}
        for uid in participant_ids:
            user_device_map[uid] = set(
                await sync_to_async(list)(
                    UserDeviceKey.objects.filter(user_id=uid, is_active=True)
                    .values_list("device_id", flat=True)
                )
            )

        for enc in payload.get("encrypted_contents", []):
            device_id = enc["device_id"]
            encrypted_blob = enc["encrypted_content"]

            dm_edit_data = build_dm_edit_message_data(
                payload=payload,
                device_id=device_id,
                encrypted_content=encrypted_blob,
            )

            for participant in participants:
                participant_device_ids = user_device_map.get(participant.id, set())

                if device_id not in participant_device_ids:
                    continue

                await self.channel_layer.group_send(
                    f"user_device_{participant.id}_{device_id}",
                    {
                        "type": "dispatch_event",
                        "app": "conversation",
                        "event": "edit_message",
                        "data": dm_edit_data,
                    },
                )

    # ------------------------------------------------------------
    # SOFT DELETE
    # ------------------------------------------------------------
    async def handle_soft_delete_message(self, data):
        message_id = data.get("message_id")
        user = self.user

        if not message_id:
            return

        try:
            message = await sync_to_async(
                Message.objects.select_related("dialogue").get
            )(id=message_id)
        except Message.DoesNotExist:
            await self._send_error(
                code="MESSAGE_NOT_FOUND",
                message="Message not found",
            )
            return

        await sync_to_async(lambda: message.mark_as_deleted_by_user(user))()

        dialogue_slug = message.dialogue.slug
        soft_delete_data = build_soft_delete_event_data(
            dialogue_slug=dialogue_slug,
            message_id=message.id,
            user_id=user.id,
        )

        await self.channel_layer.group_send(
            f"user_{user.id}",
            {
                "type": "dispatch_event",
                "app": "conversation",
                "event": "message_soft_deleted",
                "data": soft_delete_data,
            },
        )

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
    # HARD DELETE
    # ------------------------------------------------------------
    async def handle_hard_delete_message(self, data):
        message_id = data.get("message_id")

        if not message_id:
            return

        result = await database_sync_to_async(hard_delete_message_for_user)(
            message_id=message_id,
            acting_user=self.user,
        )

        if not result.get("ok"):
            await self._send_error(
                code=result.get("code", "HARD_DELETE_FAILED"),
                message=result.get("message", "Failed to hard delete message"),
            )
            return

        payload = result["payload"]
        hard_delete_data = build_hard_delete_event_data(
            dialogue_slug=payload["dialogue_slug"],
            message_id=payload["message_id"],
        )

        for uid in payload["participant_ids"]:
            await self.channel_layer.group_send(
                f"user_{uid}",
                {
                    "type": "dispatch_event",
                    "app": "conversation",
                    "event": "message_hard_deleted",
                    "data": hard_delete_data,
                },
            )

        for uid in payload["participant_ids"]:
            await self.channel_layer.group_send(
                f"user_{uid}",
                {
                    "type": "dispatch_event",
                    "app": "conversation",
                    "event": "trigger_unread_count_update",
                    "data": {},
                },
            )