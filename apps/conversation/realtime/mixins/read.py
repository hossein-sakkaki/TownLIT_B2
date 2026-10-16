# apps/conversation/realtime/mixins/read.py
# TownLIT-Backend
#
# Last Update by Hossein Sakkaki on 2026-10-06.
#

import logging

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async

from apps.conversation.models import Dialogue
from apps.conversation.policies import (
    ConversationContextKind,
    ConversationContextPolicy,
)
from apps.conversation.services.event_contracts import (
    build_read_event_data,
    build_unread_snapshot_event_data,
)
from apps.conversation.services.read_delivery import mark_dialogue_read_for_user
from apps.conversation.services.organization.direct_realtime import (
    organization_messenger_unread_snapshot_for_user,
)

logger = logging.getLogger(__name__)


class ReadMixin:
    """Conversation read/unread tracking with Organization reconciliation."""

    async def mark_message_as_read(self, data):
        if getattr(self, "_processing_read", False):
            return
        if not getattr(self, "connected", False):
            return

        self._processing_read = True
        try:
            dialogue_slug = data.get("dialogue_slug")
            source = data.get("source", "frontend")

            result = await database_sync_to_async(mark_dialogue_read_for_user)(
                dialogue_slug,
                self.user,
            )
            if not result.get("ok"):
                return

            payload = result["payload"]
            read_message_ids = payload.get("read_messages", [])

            # Organization Direct dispatches its privacy-safe read events from
            # the shared service so REST and WebSocket paths behave identically.
            if payload.get("organization_direct"):
                if source == "frontend":
                    await self.send_unread_counts()
                return

            if not read_message_ids:
                if source == "frontend":
                    await self.send_unread_counts()
                return

            read_data = build_read_event_data(payload=payload)

            dialogue = await sync_to_async(Dialogue.objects.get)(
                slug=dialogue_slug,
                participants=self.user,
            )
            context = await database_sync_to_async(
                ConversationContextPolicy.resolve
            )(dialogue)

            if context.kind == ConversationContextKind.ORGANIZATION_MEMBERS_COMMUNITY:
                participant_ids = await sync_to_async(list)(
                    dialogue.participants.exclude(id=self.user.id)
                    .values_list("id", flat=True)
                )
            else:
                participant_ids = await sync_to_async(list)(
                    dialogue.participants.exclude(id=self.user.id)
                    .values_list("id", flat=True)
                )

            for uid in participant_ids:
                await self.channel_layer.group_send(
                    f"user_{uid}",
                    {
                        "type": "dispatch_event",
                        "app": "conversation",
                        "event": "mark_as_read",
                        "data": read_data,
                    },
                )

            if source == "frontend":
                await self.send_unread_counts()

        finally:
            self._processing_read = False

    async def send_unread_counts(self):
        if not getattr(self, "connected", False):
            return

        user = self.user
        try:
            dialogues = await sync_to_async(list)(
                Dialogue.objects.filter(participants=user)
                .exclude(deleted_by_users=user)
            )

            results = []
            for dialogue in dialogues:
                unread_count = await sync_to_async(
                    lambda d=dialogue: d.unread_messages_for_user(user).count()
                )()
                results.append({
                    "dialogue_slug": dialogue.slug,
                    "unread_count": unread_count,
                })

            if not getattr(self, "connected", False):
                return

            await self.consumer.send_app_event(
                app="conversation",
                event="unread_count_update",
                data=build_unread_snapshot_event_data(results=results),
            )

            organization_snapshot = await database_sync_to_async(
                organization_messenger_unread_snapshot_for_user
            )(user)
            await self.consumer.send_app_event(
                app="conversation",
                event="organization_messenger_unread_update",
                data=organization_snapshot,
            )

        except Exception as exc:
            logger.warning("[ReadMixin] send_unread_counts failed: %s", exc)
            self.connected = False

    async def trigger_unread_count_update(self, event):
        await self.send_unread_counts()
