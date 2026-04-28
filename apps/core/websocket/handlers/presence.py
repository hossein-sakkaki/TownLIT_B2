# apps/core/websocket/handlers/presence.py
# =========================================================
#                    Presence Handler
# =========================================================

from __future__ import annotations

import logging

from channels.db import database_sync_to_async

from apps.accounts.models.devices import UserDeviceKey
from apps.core.websocket.services.presence_lifecycle import (
    mark_user_online,
    mark_user_offline,
)
from apps.core.websocket.services.presence_queries import get_presence_snapshot
from apps.core.websocket.services.presence_broadcast import (
    broadcast_user_online_status,
    broadcast_user_last_seen,
)

logger = logging.getLogger(__name__)


class PresenceHandler:
    """
    Presence domain owner for:
    - online/offline lifecycle
    - last seen
    - snapshot requests
    - presence event dispatching

    Notes:
    - Socket heartbeat/pong is owned by CentralWebSocketConsumer.
    - This handler only manages presence domain commands/events.
    """

    APP = "presence"

    def __init__(self, consumer):
        self.consumer = consumer
        self.user = consumer.user
        self.device_id = consumer.device_id
        self.channel_layer = consumer.channel_layer
        self.channel_name = consumer.channel_name

        self.connected = False
        self._finalized = False
        self.force_logout_triggered = False

    # -----------------------------------------------------
    # Helpers
    # -----------------------------------------------------
    def _message_data(self, message: dict) -> dict:
        """
        Canonical app payload accessor.
        """
        data = message.get("data")
        if isinstance(data, dict):
            return data
        return {}

    async def _send_error(self, code: str, message: str, details: dict | None = None):
        await self.consumer.send_app_error(
            app=self.APP,
            code=code,
            message=message,
            details=details,
        )

    async def _send_presence_event(self, event_type: str, data: dict):
        await self.consumer.send_app_event(
            app=self.APP,
            event=event_type,
            data=data,
        )

    # -----------------------------------------------------
    # Connect
    # -----------------------------------------------------
    async def on_connect(self):
        self.user = self.consumer.user
        self.device_id = self.consumer.device_id
        self.connected = True

        if not self.user or not self.user.is_authenticated or not self.device_id:
            await self.consumer.close()
            return

        belongs = await database_sync_to_async(
            UserDeviceKey.objects.filter(
                user=self.user,
                device_id=self.device_id,
                is_active=True,
            ).exists
        )()

        logger.info(
            "[Presence] WS connect user=%s device_id=%s belongs=%s",
            getattr(self.user, "id", None),
            self.device_id,
            belongs,
        )

        if not belongs:
            await self.consumer.close(code=4403)
            return

        # Keep using channel groups directly for presence ownership
        try:
            await self.channel_layer.group_add(f"user_{self.user.id}", self.channel_name)
        except Exception as exc:
            logger.error(f"[Presence] failed to join user group: {exc}", exc_info=True)

        try:
            await self.channel_layer.group_add(f"device_{self.device_id}", self.channel_name)
        except Exception as exc:
            logger.error(f"[Presence] failed to join device group: {exc}", exc_info=True)

        await mark_user_online(self.user.id, self.channel_name)
        await broadcast_user_online_status(self.user.id, True)

    # -----------------------------------------------------
    # Disconnect
    # -----------------------------------------------------
    async def on_disconnect(self):
        await self.disconnect()

    async def disconnect(self):
        if self._finalized:
            return

        self._finalized = True
        self.connected = False

        try:
            payload = await mark_user_offline(self.user.id, self.channel_name)
        except Exception as exc:
            logger.error(f"[Presence] mark_user_offline failed: {exc}", exc_info=True)
            payload = None

        try:
            await self.channel_layer.group_discard(f"user_{self.user.id}", self.channel_name)
        except Exception as exc:
            logger.error(f"[Presence] failed to leave user group: {exc}", exc_info=True)

        if self.device_id:
            try:
                await self.channel_layer.group_discard(
                    f"device_{self.device_id}",
                    self.channel_name,
                )
            except Exception as exc:
                logger.error(f"[Presence] failed to leave device group: {exc}", exc_info=True)

        if payload is not None:
            try:
                await broadcast_user_online_status(self.user.id, False)
                await broadcast_user_last_seen(self.user.id, payload)
            except Exception as exc:
                logger.error(
                    f"[Presence] broadcast offline/last_seen failed: {exc}",
                    exc_info=True,
                )

    # -----------------------------------------------------
    # Client messages
    # -----------------------------------------------------
    async def handle(self, message: dict):
        """
        Handle client -> server presence messages.
        Canonical incoming shape:
            {
                "app": "presence",
                "type": "...",
                "data": {...}
            }
        """
        msg_type = message.get("type")
        data = self._message_data(message)

        if msg_type == "request_presence_snapshot":
            await self.handle_request_presence_snapshot(data)
            return

        await self._send_error(
            code="UNSUPPORTED_MESSAGE_TYPE",
            message=f"Unsupported presence message type '{msg_type}'",
        )

    async def handle_request_presence_snapshot(self, data: dict):
        """
        Return a presence snapshot for a list of users.
        """
        raw_ids = data.get("user_ids") or []
        if not isinstance(raw_ids, list):
            raw_ids = []

        snapshot = await get_presence_snapshot(raw_ids)

        await self._send_presence_event(
            "presence_snapshot",
            {
                "statuses": {str(k): bool(v) for k, v in snapshot.items()},
            },
        )

    # -----------------------------------------------------
    # Backend event dispatcher
    # -----------------------------------------------------
    async def handle_backend_event(self, payload: dict):
        """
        Forward backend presence events to client.
        """
        event_type = payload.get("event")
        data = payload.get("data", {}) or {}

        if event_type == "user_online_status":
            await self._send_presence_event("user_online_status", data)
            return

        if event_type == "user_last_seen":
            await self._send_presence_event("user_last_seen", data)
            return

        if event_type == "presence_snapshot":
            await self._send_presence_event("presence_snapshot", data)
            return

        if event_type == "force_logout":
            await self.force_logout(data)
            return

        logger.warning(f"[PresenceHandler] Unknown backend event: {event_type}")

    # -----------------------------------------------------
    # Force logout
    # -----------------------------------------------------
    async def force_logout(self, event: dict):
        if int(event.get("user_id") or 0) != self.user.id:
            return

        self.force_logout_triggered = True
        await self.disconnect()
        await self.consumer.close()