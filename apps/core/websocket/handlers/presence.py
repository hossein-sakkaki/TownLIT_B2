# apps/core/websocket/handlers/presence.py
# =========================================================
#                    Presence Handler
# =========================================================

from __future__ import annotations

import logging

from channels.db import database_sync_to_async
from django.db.models import Q

from apps.accounts.models.devices import UserDeviceKey
from apps.core.boundaries.constants import BOUNDARY_BOUNDARY
from apps.core.boundaries.models import UserBoundary
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

    Boundary rule:
    - If a Boundary exists between viewer and target, do NOT expose online status.
    - If a Boundary exists between viewer and target, do NOT expose last seen.
    - Stillness does NOT hide presence.
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

    async def _send_error(
        self,
        code: str,
        message: str,
        details: dict | None = None,
    ):
        await self.consumer.send_app_error(
            app=self.APP,
            code=code,
            message=message,
            details=details,
        )

    async def _send_presence_event(
        self,
        event_type: str,
        data: dict,
    ):
        await self.consumer.send_app_event(
            app=self.APP,
            event=event_type,
            data=data,
        )

    def _authenticated_user_id(self) -> int | None:
        if not self.user or not self.user.is_authenticated:
            return None

        try:
            return int(self.user.id)
        except Exception:
            return None

    @database_sync_to_async
    def _boundary_hidden_target_ids(
        self,
        target_ids: list[int],
    ) -> set[int]:
        """
        Return target user IDs whose presence must be hidden from self.user
        because a Boundary exists in either direction.

        Only Boundary hides presence.
        Stillness intentionally does not hide presence.
        """
        viewer_id = self._authenticated_user_id()
        if not viewer_id:
            return set()

        normalized_target_ids = {
            int(value)
            for value in target_ids
            if value and int(value) > 0 and int(value) != viewer_id
        }

        if not normalized_target_ids:
            return set()

        rows = (
            UserBoundary.objects
            .filter(
                is_active=True,
                boundary_type=BOUNDARY_BOUNDARY,
            )
            .filter(
                Q(owner_id=viewer_id, target_id__in=normalized_target_ids)
                |
                Q(target_id=viewer_id, owner_id__in=normalized_target_ids)
            )
            .values_list("owner_id", "target_id")
        )

        hidden_ids: set[int] = set()

        for owner_id, target_id in rows:
            if owner_id == viewer_id:
                hidden_ids.add(int(target_id))
            elif target_id == viewer_id:
                hidden_ids.add(int(owner_id))

        return hidden_ids

    async def _is_presence_hidden_for_target(
        self,
        target_user_id: int | None,
    ) -> bool:
        if not target_user_id:
            return False

        hidden_ids = await self._boundary_hidden_target_ids([int(target_user_id)])
        return int(target_user_id) in hidden_ids

    def _int_value(self, raw) -> int | None:
        try:
            value = int(raw)
        except Exception:
            return None

        return value if value > 0 else None

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

        try:
            await self.channel_layer.group_add(
                f"user_{self.user.id}",
                self.channel_name,
            )
        except Exception as exc:
            logger.error(
                "[Presence] failed to join user group: %s",
                exc,
                exc_info=True,
            )

        try:
            await self.channel_layer.group_add(
                f"device_{self.device_id}",
                self.channel_name,
            )
        except Exception as exc:
            logger.error(
                "[Presence] failed to join device group: %s",
                exc,
                exc_info=True,
            )

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
            logger.error(
                "[Presence] mark_user_offline failed: %s",
                exc,
                exc_info=True,
            )
            payload = None

        try:
            await self.channel_layer.group_discard(
                f"user_{self.user.id}",
                self.channel_name,
            )
        except Exception as exc:
            logger.error(
                "[Presence] failed to leave user group: %s",
                exc,
                exc_info=True,
            )

        if self.device_id:
            try:
                await self.channel_layer.group_discard(
                    f"device_{self.device_id}",
                    self.channel_name,
                )
            except Exception as exc:
                logger.error(
                    "[Presence] failed to leave device group: %s",
                    exc,
                    exc_info=True,
                )

        if payload is not None:
            try:
                await broadcast_user_online_status(self.user.id, False)
                await broadcast_user_last_seen(self.user.id, payload)
            except Exception as exc:
                logger.error(
                    "[Presence] broadcast offline/last_seen failed: %s",
                    exc,
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

        Boundary privacy:
        - Hidden users are returned as offline.
        - hidden_user_ids tells iOS to clear cached last_seen too.
        """
        raw_ids = data.get("user_ids") or []
        if not isinstance(raw_ids, list):
            raw_ids = []

        target_ids: list[int] = []

        for raw_id in raw_ids:
            value = self._int_value(raw_id)
            if value is not None:
                target_ids.append(value)

        snapshot = await get_presence_snapshot(target_ids)
        hidden_ids = await self._boundary_hidden_target_ids(target_ids)

        safe_statuses: dict[str, bool] = {}

        for target_id in target_ids:
            if target_id in hidden_ids:
                safe_statuses[str(target_id)] = False
                continue

            safe_statuses[str(target_id)] = bool(snapshot.get(target_id, False))

        await self._send_presence_event(
            "presence_snapshot",
            {
                "statuses": safe_statuses,
                "hidden_user_ids": [str(value) for value in sorted(hidden_ids)],
            },
        )

    # -----------------------------------------------------
    # Backend event dispatcher
    # -----------------------------------------------------

    async def handle_backend_event(self, payload: dict):
        """
        Forward backend presence events to client.

        Boundary privacy:
        - Online status from bounded users is forced to offline.
        - Last seen from bounded users is cleared.
        """
        event_type = payload.get("event")
        data = payload.get("data", {}) or {}

        if event_type == "user_online_status":
            await self._handle_user_online_status_event(data)
            return

        if event_type == "user_last_seen":
            await self._handle_user_last_seen_event(data)
            return

        if event_type == "presence_snapshot":
            await self._handle_backend_presence_snapshot_event(data)
            return

        if event_type == "force_logout":
            await self.force_logout(data)
            return

        logger.warning("[PresenceHandler] Unknown backend event: %s", event_type)

    async def _handle_user_online_status_event(self, data: dict):
        target_user_id = self._int_value(data.get("user_id"))

        if await self._is_presence_hidden_for_target(target_user_id):
            await self._send_presence_event(
                "user_online_status",
                {
                    "user_id": target_user_id,
                    "is_online": False,
                    "presence_hidden": True,
                },
            )
            return

        await self._send_presence_event("user_online_status", data)

    async def _handle_user_last_seen_event(self, data: dict):
        target_user_id = self._int_value(data.get("user_id"))

        if await self._is_presence_hidden_for_target(target_user_id):
            await self._send_presence_event(
                "user_last_seen",
                {
                    "user_id": target_user_id,
                    "last_seen": None,
                    "presence_hidden": True,
                },
            )
            return

        await self._send_presence_event("user_last_seen", data)

    async def _handle_backend_presence_snapshot_event(self, data: dict):
        raw_statuses = data.get("statuses") or {}

        if not isinstance(raw_statuses, dict):
            raw_statuses = {}

        target_ids = []

        for raw_id in raw_statuses.keys():
            value = self._int_value(raw_id)
            if value is not None:
                target_ids.append(value)

        hidden_ids = await self._boundary_hidden_target_ids(target_ids)

        safe_statuses = {}

        for raw_id, raw_status in raw_statuses.items():
            target_id = self._int_value(raw_id)
            if target_id is None:
                continue

            if target_id in hidden_ids:
                safe_statuses[str(target_id)] = False
            else:
                safe_statuses[str(target_id)] = bool(raw_status)

        await self._send_presence_event(
            "presence_snapshot",
            {
                "statuses": safe_statuses,
                "hidden_user_ids": [str(value) for value in sorted(hidden_ids)],
            },
        )

    # -----------------------------------------------------
    # Force logout
    # -----------------------------------------------------

    async def force_logout(self, event: dict):
        if int(event.get("user_id") or 0) != self.user.id:
            return

        self.force_logout_triggered = True
        await self.disconnect()
        await self.consumer.close()