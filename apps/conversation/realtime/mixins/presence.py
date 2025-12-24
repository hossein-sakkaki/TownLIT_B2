# apps/conversation/realtime/mixins/presence.py
import json
from asgiref.sync import sync_to_async
from services.redis_online_manager import get_online_status_for_users 
from typing import Dict, Tuple
import asyncio


class PresenceMixin:
    """
    Unified presence manager:
    - On connect → notify_user_online()
    - On disconnect → notify_user_offline() + user_last_seen
    - Send all online statuses to connected user
    - Handle request_online_status (client → server)
    - Real-time presence events (user_online_status)
    """

    # ------------------------------------------------------------
    # Public API (called by consumer)
    # ------------------------------------------------------------

    async def notify_user_online(self):
        """Broadcast to all dialogue groups that this user is online."""
        await self._broadcast_presence_to_groups(is_online=True)

    async def notify_user_offline(self):
        """Broadcast to all dialogue groups that this user is offline."""
        await self._broadcast_presence_to_groups(is_online=False)

    async def send_all_online_statuses(self):
        """
        Send full presence status of all participants across all dialogues
        to the connected user.
        """
        dialogues = await self._dialogues_for_user_async()

        for dialogue in dialogues:
            participants = await sync_to_async(list)(dialogue.participants.all())
            ids = [p.id for p in participants]
            statuses = await get_online_status_for_users(ids)

            for participant in participants:
                await self._send_single_online_status(
                    dialogue_slug=dialogue.slug,
                    user_id=participant.id,
                    is_online=bool(statuses.get(participant.id, False)),
                )

    # ------------------------------------------------------------
    # Real-time events RECEIVED FROM groups
    # ------------------------------------------------------------

    async def user_online_status(self, event):
        """Real-time broadcast from other users: online/offline changed."""
        await self._send_single_online_status(
            dialogue_slug=event["dialogue_slug"],
            user_id=event["user_id"],
            is_online=event["is_online"],
        )

    async def user_last_seen(self, event):
        """Triggered only when user becomes fully offline."""
        await self.send_json({
           "type": "event",
            "app": "conversation",
            "event": "user_last_seen",
            "data": {
                "dialogue_slug": event["dialogue_slug"],
                "user_id": event["user_id"],
                "is_online": event.get("is_online", False),
                "last_seen": event.get("last_seen"),
                "last_seen_epoch": event.get("last_seen_epoch"),
                "last_seen_display": event.get("last_seen_display"),
            }
        })


    # ------------------------------------------------------------
    # REQUEST: client → "request_online_status"
    # ------------------------------------------------------------

    async def handle_request_online_status(self, dialogue_slug: str):
        """
        Called by consumer.receive().
        Returns online status of ALL participants in a specific dialogue.
        """
        if not dialogue_slug:
            return

        from apps.conversation.models import Dialogue

        try:
            dialogue = await sync_to_async(Dialogue.objects.get)(slug=dialogue_slug)
        except Dialogue.DoesNotExist:
            return

        participants = await sync_to_async(list)(dialogue.participants.all())
        ids = [p.id for p in participants]
        statuses = await get_online_status_for_users(ids)

        for participant in participants:
            await self._send_single_online_status(
                dialogue_slug=dialogue_slug,
                user_id=participant.id,
                is_online=bool(statuses.get(participant.id, False)),
            )

    # ------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------

    async def _broadcast_presence_to_groups(self, is_online: bool):
        """Broadcast presence using unified backend-event format."""
        if not hasattr(self, "group_names"):
            return

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
                        "is_online": is_online,
                    },
                },
            ) 


    async def _send_single_online_status(self, dialogue_slug: str, user_id: int, is_online: bool):
        """Unified outgoing payload for online/offline states."""
        await self.send_json({
           "type": "event",
            "app": "conversation",
            "event": "user_online_status",
            "data": {
                "dialogue_slug": dialogue_slug,
                "user_id": user_id,
                "is_online": is_online,
            },
        })


    async def _dialogues_for_user_async(self):
        """Returns all dialogues this user participates in."""
        from apps.conversation.models import Dialogue
        return await sync_to_async(list)(
            Dialogue.objects.filter(participants=self.user)
        )
