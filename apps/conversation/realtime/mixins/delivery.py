# apps/conversation/realtime/mixins/delivery.py

import json
from asgiref.sync import sync_to_async
from services.redis_online_manager import get_online_status_for_users
from services.message_atomic_utils import (
    mark_message_as_delivered_atomic,
)

class DeliveryMixin:
    """
    Handles:
    - message delivery bookkeeping
    - notifying sender when recipient comes online
    - recipient-triggered mark-as-delivered events
    """

    # ------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------

    async def mark_message_as_delivered(self, message):
        """
        Called when:
        - recipient is online during send
        - sender comes online and receives undelivered messages
        """
        recipient = await self._get_recipient(message)
        if not recipient:
            return

        if not await self._is_user_online(recipient.id):
            return  # no delivery

        await mark_message_as_delivered_atomic(message)

        # Notify current session
        await self._send_local_delivery_update(message, recipient.id)

        # Notify all sessions of sender
        await self._broadcast_delivery_to_sender(message, recipient.id)

    # ------------------------------------------------------------    
    # EVENT HANDLERS
    # ------------------------------------------------------------

    async def notify_message_delivered_to_sender(self, message):
        """
        Used when user comes online & receives undelivered messages.
        Ensures sender is notified.
        """
        recipient = await self._get_recipient(message)
        if not recipient:
            return

        await self._broadcast_delivery_to_sender(message, recipient.id)

    # ------------------------------------------------------------
    # CLIENT-TO-SERVER EVENT HANDLERS
    # ------------------------------------------------------------
    async def handle_mark_as_delivered(self, data):
        """
        Client tells server:
        "I (recipient) just received message X"
        """
        dialogue_slug = data.get("dialogue_slug")
        message_id = data.get("message_id")

        if not dialogue_slug or not message_id:
            return

        dialogue, message = await self._load_valid_dialogue_message(
            dialogue_slug, message_id
        )
        if not dialogue or not message:
            return

        # sender cannot mark delivered
        if message.sender_id == self.user.id:
            return

        # redundant?
        if message.is_delivered:
            return

        await mark_message_as_delivered_atomic(message)

        await self._broadcast_delivery_to_sender(message, self.user.id)

    # ------------------------------------------------------------
    # SERVER-TO-CLIENT EVENT HANDLERS
    # ------------------------------------------------------------
    async def mark_as_delivered(self, event):
        await self.send_json({
           "type": "event",
            "app": "conversation",
            "event": "mark_as_delivered",
            "data": {
                "dialogue_slug": event["dialogue_slug"],
                "message_id": event["message_id"],
                "user_id": event["user_id"],
                "is_delivered": True,
            }
        })


    # ------------------------------------------------------------
    # INTERNAL HELPERS
    # ------------------------------------------------------------

    async def _get_recipient(self, message):
        """Return the other participant in a DM. Safe for group fallback."""
        return await sync_to_async(
            lambda: message.dialogue.participants.exclude(id=message.sender.id).first()
        )()

    async def _is_user_online(self, user_id: int) -> bool:
        statuses = await get_online_status_for_users([user_id])
        return bool(statuses.get(user_id, False))


    async def _send_local_delivery_update(self, message, recipient_id):
        await self.send_json({
           "type": "event",
            "app": "conversation",
            "event": "mark_as_delivered",
            "data": {
                "dialogue_slug": message.dialogue.slug,
                "message_id": message.id,
                "user_id": recipient_id,
                "is_delivered": True,
            }
        })


    async def _broadcast_delivery_to_sender(self, message, recipient_id):
        await self.channel_layer.group_send(
            f"user_{message.sender.id}",
            {
                "type": "dispatch_event",
                "app": "conversation",
                "event": "mark_as_delivered",
                "data": {
                    "dialogue_slug": message.dialogue.slug,
                    "message_id": message.id,
                    "user_id": recipient_id,
                    "is_delivered": True,
                }
            }
        )


    async def _load_valid_dialogue_message(self, dialogue_slug, message_id):
        """Ensures loaded dialogue belongs to user & message belongs to dialogue."""
        from apps.conversation.models import Dialogue, Message

        try:
            dialogue = await sync_to_async(Dialogue.objects.get)(
                slug=dialogue_slug,
                participants=self.user
            )
        except Dialogue.DoesNotExist:
            return None, None

        try:
            message = await sync_to_async(Message.objects.get)(
                id=message_id,
                dialogue=dialogue
            )
        except Message.DoesNotExist:
            return dialogue, None

        return dialogue, message
 