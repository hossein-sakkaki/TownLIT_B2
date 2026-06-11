import logging

from apps.conversation.services.event_contracts import (
    build_founder_transferred_event_data,
    build_group_added_event_data,
    build_group_left_event_data,
    build_group_removed_event_data,
    build_group_updated_event_data,
)

logger = logging.getLogger(__name__)


class ConversationGroupMixin:
    """
    Handles group-level conversation events:
    - group_added
    - group_removed
    - group_left
    - founder_transferred
    - group_updated

    Production notes:
    - user_{id} targeted events are used for membership changes.
    - removed users must be discarded from dialogue_{slug} immediately
      so they do not keep receiving group messages until reconnect.
    """

    async def _send_group_event(self, event_name: str, data: dict):
        await self.consumer.send_app_event(
            app="conversation",
            event=event_name,
            data=data,
        )

    async def _discard_dialogue_group_if_present(self, dialogue_slug: str | None):
        """
        Remove this socket from one dialogue group if the backend tells us
        this user no longer belongs to that group.
        """
        if not dialogue_slug:
            return

        group_name = f"dialogue_{dialogue_slug}"

        try:
            await self.channel_layer.group_discard(
                group_name,
                self.channel_name,
            )

            self.group_names.discard(group_name)
            self.dialogue_map.pop(group_name, None)

            logger.info(
                "[Conversation] discarded socket from %s after membership removal.",
                group_name,
            )
        except Exception as exc:
            logger.exception(
                "[Conversation] failed to discard socket from %s: %s",
                group_name,
                exc,
            )

    async def group_added(self, event):
        data = build_group_added_event_data(
            dialogue=event.get("dialogue"),
        )

        await self._send_group_event(
            "group_added",
            data,
        )

        dialogue = data.get("dialogue") or {}
        dialogue_slug = dialogue.get("slug")

        if dialogue_slug:
            group_name = f"dialogue_{dialogue_slug}"

            try:
                await self.consumer.join_feature_group(group_name)
                self.group_names.add(group_name)

                if dialogue.get("id"):
                    self.dialogue_map[group_name] = dialogue.get("id")

            except Exception as exc:
                logger.exception(
                    "[Conversation] failed to join newly added group %s: %s",
                    group_name,
                    exc,
                )

    async def group_removed(self, event):
        data = build_group_removed_event_data(
            dialogue=event.get("dialogue"),
        )

        await self._send_group_event(
            "group_removed",
            data,
        )

        dialogue = data.get("dialogue") or {}
        dialogue_slug = dialogue.get("slug")

        await self._discard_dialogue_group_if_present(dialogue_slug)

    async def group_left(self, event):
        data = build_group_left_event_data(
            user=event.get("user"),
            dialogue_slug=event.get("dialogue_slug"),
        )

        await self._send_group_event(
            "group_left",
            data,
        )

    async def founder_transferred(self, event):
        await self._send_group_event(
            "founder_transferred",
            build_founder_transferred_event_data(
                dialogue_slug=event.get("dialogue_slug"),
                new_founder_id=event.get("new_founder_id"),
            ),
        )

    async def group_updated(self, event):
        await self._send_group_event(
            "group_updated",
            build_group_updated_event_data(
                dialogue_slug=event.get("dialogue_slug"),
                reason=event.get("reason") or "group_updated",
                dialogue=event.get("dialogue"),
                actor_id=event.get("actor_id"),
                target_user_id=event.get("target_user_id"),
            ),
        )