# apps/conversation/realtime/mixins/group_events.py

import logging

from apps.conversation.services.event_contracts import (
    build_founder_transferred_event_data,
    build_group_added_event_data,
    build_group_left_event_data,
    build_group_removed_event_data,
)

logger = logging.getLogger(__name__)


class ConversationGroupMixin:
    """
    Handles group-level conversation events:
    - group_added
    - group_removed
    - group_left
    - founder_transferred
    """

    async def _send_group_event(self, event_name: str, data: dict):
        await self.consumer.send_app_event(
            app="conversation",
            event=event_name,
            data=data,
        )

    async def group_added(self, event):
        await self._send_group_event(
            "group_added",
            build_group_added_event_data(
                dialogue=event.get("dialogue"),
            ),
        )

    async def group_removed(self, event):
        await self._send_group_event(
            "group_removed",
            build_group_removed_event_data(
                dialogue=event.get("dialogue"),
            ),
        )

    async def group_left(self, event):
        await self._send_group_event(
            "group_left",
            build_group_left_event_data(
                user=event.get("user"),
                dialogue_slug=event.get("dialogue_slug"),
            ),
        )

    async def founder_transferred(self, event):
        await self._send_group_event(
            "founder_transferred",
            build_founder_transferred_event_data(
                dialogue_slug=event.get("dialogue_slug"),
                new_founder_id=event.get("new_founder_id"),
            ),
        )