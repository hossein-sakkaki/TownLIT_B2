# apps/conversation/realtime/read.py

import json
import logging
from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async

from apps.conversation.models import Dialogue, Message
from services.message_atomic_utils import mark_message_as_read_atomic

logger = logging.getLogger(__name__)


class ReadMixin:
    """
    Safe unread/read tracking system with:
    - re-entry guard
    - connection safety guard
    - backend/frontend separation
    """

    # -------------------------------------------------------------
    # 1) CLIENT REQUEST → MARK AS READ
    # -------------------------------------------------------------
    async def mark_message_as_read(self, data):

        # 🔒 Prevent recursion
        if getattr(self, "_processing_read", False):
            return

        # 🔒 If connection is closed: do nothing
        if not getattr(self, "connected", False):
            return

        self._processing_read = True
        try:
            dialogue_slug = data.get("dialogue_slug")
            source = data.get("source", "frontend")

            if not dialogue_slug:
                return

            try:
                dialogue = await sync_to_async(Dialogue.objects.get)(slug=dialogue_slug)
            except Dialogue.DoesNotExist:
                return

            # unread messages for this user
            unread_messages = await sync_to_async(list)(
                Message.objects.filter(dialogue=dialogue)
                .exclude(seen_by_users=self.user)
            )

            # atomic marking
            for message in unread_messages:
                if message.sender_id == self.user.id:
                    continue
                await mark_message_as_read_atomic(message, self.user)

            # -------------------------------------------------
            # SEND READ RECEIPT TO OTHER PARTICIPANTS
            # -------------------------------------------------
            participants = await sync_to_async(
                lambda: list(
                    dialogue.participants
                        .exclude(id=self.user.id)
                        .values_list("id", flat=True)
                )
            )()

            payload = {
                "dialogue_slug": dialogue_slug,
                "reader": {
                    "id": self.user.id,
                    "username": self.user.username,
                    "email": self.user.email,
                },
                "read_messages": [
                    msg.id for msg in unread_messages
                    if msg.sender_id != self.user.id
                ],
            }

            for uid in participants:
                await self.channel_layer.group_send( 
                    f"user_{uid}",
                    {
                        "type": "dispatch_event",
                        "app": "conversation",
                        "event": "mark_as_read",
                        "data": payload,
                    }
                )

            # -------------------------------------------------
            # Only FRONTEND events should trigger unread_count push
            # -------------------------------------------------
            if source == "frontend":
                await self.send_unread_counts()

        finally:
            self._processing_read = False



    # -------------------------------------------------------------
    # 3) CALCULATE & PUSH UNREAD COUNTS TO USER
    # -------------------------------------------------------------
    async def send_unread_counts(self):

        if not getattr(self, "connected", False):
            return

        user = self.user

        try:
            dialogues = await sync_to_async(list)(
                Dialogue.objects.filter(participants=user)
            )

            results = []
            for dialogue in dialogues:
                unread_count = await sync_to_async(
                    lambda: dialogue.messages
                        .exclude(seen_by_users=user)
                        .exclude(sender=user)
                        .count()
                )()

                results.append({
                    "dialogue_slug": dialogue.slug,
                    "unread_count": unread_count,
                })

            if getattr(self, "connected", False):
                await self.send_json({
                    "type": "unread_count_update",
                    "payload": results,
                })

        except Exception as e:
            # If WS is closed, prevent future sends
            logger.warning(f"[ReadMixin] send_unread_counts failed: {e}")
            self.connected = False
            return


    # -------------------------------------------------------------
    # 4) GENERIC "trigger_unread_count_update" (backend)
    # -------------------------------------------------------------
    async def trigger_unread_count_update(self, event):
        await self.send_unread_counts()
