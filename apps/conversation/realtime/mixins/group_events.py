# apps/conversation/realtime/group_events.py
import logging

logger = logging.getLogger(__name__)


class ConversationGroupMixin:
    """
    Handles system-level group events for dialogues:
    - group_added
    - group_removed
    - group_left
    - founder_transferred
    """

    async def _send_event(self, event_name: str, data: dict):
        # Unified envelope for frontend websocketManager
        await self.send_json({
            "type": "event",
            "app": "conversation",
            "event": event_name,
            "data": data,
        })

    # ---------------------------------------------------------
    async def group_added(self, event):
        await self._send_event("group_added", {
            "dialogue": event.get("dialogue")
        })

    # ---------------------------------------------------------
    async def group_removed(self, event):
        await self._send_event("group_removed", {
            "dialogue": event.get("dialogue")
        })

    # ---------------------------------------------------------
    async def group_left(self, event):
        await self._send_event("group_left", {
            "user": event.get("user"),
            "dialogue_slug": event.get("dialogue_slug"),
        })

    # ---------------------------------------------------------
    async def founder_transferred(self, event):
        await self._send_event("founder_transferred", {
            "dialogue_slug": event.get("dialogue_slug"),
            "new_founder_id": event.get("new_founder_id"),
        })
