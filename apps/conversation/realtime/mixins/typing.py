# apps/conversation/realtime/mixins/typing.py

import asyncio

from apps.conversation.services.event_contracts import build_typing_status_event_data

TYPING_TIMEOUTS = {}


def build_typing_timeout_key(user_id: int, dialogue_slug: str):
    """Build a stable timeout key."""
    return (user_id, dialogue_slug)


def cancel_typing_timeout(key):
    """Cancel one typing timeout safely."""
    task = TYPING_TIMEOUTS.pop(key, None)
    if not task:
        return

    try:
        task.cancel()
    except Exception:
        pass


def cancel_all_typing_timeouts_for_user(user_id: int):
    """Cancel all typing timeouts for one user safely."""
    for key in list(TYPING_TIMEOUTS.keys()):
        if not isinstance(key, tuple) or len(key) != 2:
            continue

        timeout_user_id, _dialogue_slug = key
        if timeout_user_id != user_id:
            continue

        cancel_typing_timeout(key)


class TypingMixin:
    """
    Handles typing events for conversation realtime.
    """

    TYPING_DURATION = 5  # seconds

    async def handle_typing_status(self, data):
        dialogue_slug = (data.get("dialogue_slug") or "").strip()
        is_typing = bool(data.get("is_typing", False))

        if not dialogue_slug:
            return

        await self._broadcast_typing_status(dialogue_slug, is_typing)

        if is_typing:
            await self._schedule_typing_clear(dialogue_slug)
        else:
            key = build_typing_timeout_key(self.user.id, dialogue_slug)
            cancel_typing_timeout(key)

    async def _broadcast_typing_status(self, dialogue_slug: str, is_typing: bool):
        payload = build_typing_status_event_data(
            dialogue_slug=dialogue_slug,
            user=self.user,
        )
        payload["is_typing"] = is_typing

        await self.channel_layer.group_send(
            f"dialogue_{dialogue_slug}",
            {
                "type": "dispatch_event",
                "app": "conversation",
                "event": "typing_status",
                "data": payload,
            },
        )

    async def _schedule_typing_clear(self, dialogue_slug: str):
        key = build_typing_timeout_key(self.user.id, dialogue_slug)
        cancel_typing_timeout(key)

        TYPING_TIMEOUTS[key] = asyncio.create_task(
            self._clear_typing_after_timeout(dialogue_slug)
        )

    async def _clear_typing_after_timeout(self, dialogue_slug: str):
        try:
            await asyncio.sleep(self.TYPING_DURATION)
        except asyncio.CancelledError:
            return

        await self._broadcast_typing_status(dialogue_slug, is_typing=False)

        key = build_typing_timeout_key(self.user.id, dialogue_slug)
        TYPING_TIMEOUTS.pop(key, None)