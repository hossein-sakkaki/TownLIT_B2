# apps/conversation/realtime/mixins/delivery.py
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async

from apps.core.websocket.services.redis_online_manager import get_online_status_for_users
from apps.conversation.services.message_atomic_utils import mark_message_as_delivered_atomic
from apps.conversation.services.read_delivery import mark_message_delivered_for_user
from apps.conversation.services.event_contracts import build_delivery_event_data


class DeliveryMixin:
    """
    Handles:
    - message delivery bookkeeping
    - notifying sender when recipient comes online
    - recipient-triggered mark-as-delivered events
    """

    async def mark_message_as_delivered(self, message):
        """
        Called when:
        - recipient is online during send
        - recipient receives undelivered message replay

        Canonical semantics:
        - persist delivered state
        - notify sender sessions only
        """
        recipient = await self._get_recipient(message)
        if not recipient:
            return

        await mark_message_as_delivered_atomic(message)

        if not await self._is_user_online(recipient.id):
            return

        await self._broadcast_delivery_to_sender(message, recipient.id)

    async def notify_message_delivered_to_sender(self, message):
        """
        Ensure sender receives delivery update.
        """
        recipient = await self._get_recipient(message)
        if not recipient:
            return

        await self._broadcast_delivery_to_sender(message, recipient.id)

    async def handle_mark_as_delivered(self, data):
        """
        Client tells server:
        'I just received this message'
        """
        result = await database_sync_to_async(mark_message_delivered_for_user)(
            data.get("dialogue_slug"),
            data.get("message_id"),
            self.user,
        )

        if not result.get("ok"):
            return

        payload = result["payload"]
        await self._broadcast_delivery_to_sender_by_payload(payload)

    async def mark_as_delivered(self, event):
        await self.consumer.send_app_event(
            app="conversation",
            event="mark_as_delivered",
            data=build_delivery_event_data(
                dialogue_slug=event["dialogue_slug"],
                message_id=event["message_id"],
                user_id=event["user_id"],
                is_delivered=True,
            ),
        )

    async def _get_recipient(self, message):
        return await sync_to_async(
            lambda: message.dialogue.participants.exclude(id=message.sender.id).first()
        )()

    async def _is_user_online(self, user_id: int) -> bool:
        statuses = await get_online_status_for_users([user_id])
        return bool(statuses.get(user_id, False))

    async def _broadcast_delivery_to_sender(self, message, recipient_id):
        await self.channel_layer.group_send(
            f"user_{message.sender.id}",
            {
                "type": "dispatch_event",
                "app": "conversation",
                "event": "mark_as_delivered",
                "data": build_delivery_event_data(
                    dialogue_slug=message.dialogue.slug,
                    message_id=message.id,
                    user_id=recipient_id,
                    is_delivered=True,
                ),
            },
        )

    async def _load_valid_dialogue_message(self, dialogue_slug, message_id):
        from apps.conversation.models import Dialogue, Message

        try:
            dialogue = await sync_to_async(Dialogue.objects.get)(
                slug=dialogue_slug,
                participants=self.user,
            )
        except Dialogue.DoesNotExist:
            return None, None

        try:
            message = await sync_to_async(Message.objects.get)(
                id=message_id,
                dialogue=dialogue,
            )
        except Message.DoesNotExist:
            return dialogue, None

        return dialogue, message

    async def _broadcast_delivery_to_sender_by_payload(self, payload):
        await self.channel_layer.group_send(
            f"user_{payload['sender_id']}",
            {
                "type": "dispatch_event",
                "app": "conversation",
                "event": "mark_as_delivered",
                "data": build_delivery_event_data(
                    dialogue_slug=payload["dialogue_slug"],
                    message_id=payload["message_id"],
                    user_id=payload["user_id"],
                    is_delivered=payload["is_delivered"],
                ),
            },
        )