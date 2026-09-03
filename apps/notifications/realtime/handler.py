# apps/notifications/realtime/handler.py

import logging

from channels.db import database_sync_to_async

from apps.notifications.constants import (
    NOTIFICATION_TYPES_EXCLUDED_FROM_GENERAL_UNREAD,
)
from apps.notifications.models import Notification


logger = logging.getLogger(__name__)


class NotificationsHandler:
    """
    Canonical WebSocket handler for notifications.
    """

    APP = "notifications"

    def __init__(self, socket):
        self.socket = socket
        self.user = socket.user
        self.group = f"notif_user_{self.user.id}"

    # ------------------------------------------------------
    # Helpers
    # ------------------------------------------------------

    def _message_data(self, message: dict) -> dict:
        data = message.get("data")

        if isinstance(data, dict):
            return data

        return {}

    async def _send_event(
        self,
        event: str,
        data: dict | None = None,
    ):
        await self.socket.send_app_event(
            app=self.APP,
            event=event,
            data=data or {},
        )

    async def _send_error(
        self,
        code: str,
        message: str,
        details: dict | None = None,
    ):
        await self.socket.send_app_error(
            app=self.APP,
            code=code,
            message=message,
            details=details,
        )

    @database_sync_to_async
    def _general_unread_count(self) -> int:
        return (
            Notification.objects
            .filter(
                user_id=self.user.id,
                is_read=False,
            )
            .exclude(
                notification_type__in=(
                    NOTIFICATION_TYPES_EXCLUDED_FROM_GENERAL_UNREAD
                )
            )
            .count()
        )

    # ------------------------------------------------------
    # Connect / Disconnect
    # ------------------------------------------------------

    async def on_connect(self):
        try:
            await self.socket.join_feature_group(
                self.group
            )

        except Exception as error:
            logger.error(
                "[NotifHandler] join %s failed: %s",
                self.group,
                error,
                exc_info=True,
            )

            await self._send_error(
                code="NOTIFICATION_GROUP_JOIN_FAILED",
                message=(
                    "Notifications realtime could not be initialized."
                ),
            )

            return

        ready_payload = {
            "status": "ok",
        }

        try:
            ready_payload["unread"] = (
                await self._general_unread_count()
            )

        except Exception:
            logger.warning(
                "[NotifHandler] unread bootstrap failed "
                "user=%s",
                self.user.id,
                exc_info=True,
            )

        
        # Do not send ready before group join succeeds.
        await self._send_event(
            "ready",
            ready_payload,
        )

    async def on_disconnect(self):
        try:
            await self.socket.leave_feature_group(
                self.group
            )

        except Exception as error:
            logger.warning(
                "[NotifHandler] leave %s failed: %s",
                self.group,
                error,
                exc_info=True,
            )

    # ------------------------------------------------------
    # Client -> Server
    # ------------------------------------------------------

    async def handle(self, message: dict):
        msg_type = message.get("type")
        data = self._message_data(message)

        if msg_type == "delivered":
            await self._mark_delivered(
                data
            )
            return

        await self._send_error(
            code="UNSUPPORTED_MESSAGE_TYPE",
            message=(
                "Unsupported notifications message "
                f"type '{msg_type}'"
            ),
        )

    async def _mark_delivered(
        self,
        data: dict,
    ):
        await self._send_event(
            "delivered_ack",
            {
                "status": "ok",
                **(data or {}),
            },
        )

    # ------------------------------------------------------
    # Backend -> Client
    # ------------------------------------------------------

    async def handle_backend_event(
        self,
        event: dict,
    ):
        event_type = event.get(
            "event"
        )

        data = (
            event.get(
                "data",
                {},
            )
            or {}
        )

        if not event_type:
            logger.warning(
                "[NotifHandler] Missing backend event type"
            )
            return

        await self._send_event(
            event_type,
            data,
        )