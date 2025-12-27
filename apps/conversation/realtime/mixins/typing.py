import asyncio
import json

TYPING_TIMEOUTS = {}

class TypingMixin:
    """
    Handles typing events without infinite loops.
    Client → Server:      "typing_status"
    Server → Broadcast:   "typing_status_broadcast"
    """

    TYPING_DURATION = 5  # seconds

    # --------------------------------------------------------------------
    # 1) Client → server event
    # --------------------------------------------------------------------
    async def handle_typing_status(self, data):
        dialogue_slug = data.get("dialogue_slug")
        is_typing = data.get("is_typing", False)

        if not dialogue_slug:
            return

        # Broadcast typing updates (now safe, no loop)
        await self._broadcast_typing_status(dialogue_slug, is_typing)

        # Auto-stop typing
        if is_typing:
            await self._schedule_typing_clear(dialogue_slug)


    # --------------------------------------------------------------------
    # Internal: broadcast typing to dialogue group
    # --------------------------------------------------------------------
    async def _broadcast_typing_status(self, dialogue_slug: str, is_typing: bool):
        """Unified safe broadcast → DOES NOT re-trigger handle_typing_status."""
        await self.channel_layer.group_send(
            f"dialogue_{dialogue_slug}",
            {
                "type": "dispatch_event",
                "app": "conversation",
                "event": "typing_status_broadcast",   # IMPORTANT!
                "data": {
                    "dialogue_slug": dialogue_slug,
                    "sender": {
                        "id": self.user.id,
                        "username": self.user.username,
                        "email": self.user.email,
                    },
                    "is_typing": is_typing,
                },
            }
        )

    # --------------------------------------------------------------------
    # Auto-clear typing after timeout
    # --------------------------------------------------------------------
    async def _schedule_typing_clear(self, dialogue_slug: str):
        key = (self.user.id, dialogue_slug)

        if TYPING_TIMEOUTS.get(key):
            TYPING_TIMEOUTS[key].cancel()

        TYPING_TIMEOUTS[key] = asyncio.create_task(
            self._clear_typing_after_timeout(dialogue_slug)
        )


    async def _clear_typing_after_timeout(self, dialogue_slug: str):
        try:
            await asyncio.sleep(self.TYPING_DURATION)
        except asyncio.CancelledError:
            return

        await self._broadcast_typing_status(dialogue_slug, is_typing=False)

        TYPING_TIMEOUTS.pop((self.user.id, dialogue_slug), None)
