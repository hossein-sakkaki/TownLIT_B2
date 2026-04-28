# apps/notifications/realtime/handler.py
import logging

logger = logging.getLogger(__name__)


class NotificationsHandler:
    """
    Canonical WS handler for notifications.

    Client -> Server:
        { "app": "notifications", "type": "delivered", "data": {...} }

    Server -> Client:
        { "app": "notifications", "type": "event", "event": "...", "data": {...} }

    Notes:
    - Socket heartbeat/ping/pong is owned by CentralWebSocketConsumer.
    - This handler only manages notification domain events.
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

    async def _send_event(self, event: str, data: dict | None = None):
        await self.socket.send_app_event(
            app=self.APP,
            event=event,
            data=data or {},
        )

    async def _send_error(self, code: str, message: str, details: dict | None = None):
        await self.socket.send_app_error(
            app=self.APP,
            code=code,
            message=message,
            details=details,
        )

    # ------------------------------------------------------
    # Connect / Disconnect
    # ------------------------------------------------------
    async def on_connect(self):
        try:
            await self.socket.join_feature_group(self.group)
        except Exception as e:
            logger.error(f"[NotifHandler] join {self.group} failed: {e}", exc_info=True)

        # Canonical ready event
        await self._send_event("ready", {"status": "ok"})

    async def on_disconnect(self):
        try:
            await self.socket.leave_feature_group(self.group)
        except Exception as e:
            logger.error(f"[NotifHandler] leave {self.group} failed: {e}", exc_info=True)

    # ------------------------------------------------------
    # Client -> Server
    # ------------------------------------------------------
    async def handle(self, message: dict):
        msg_type = message.get("type")
        data = self._message_data(message)

        if msg_type == "delivered":
            await self._mark_delivered(data)
            return

        await self._send_error(
            code="UNSUPPORTED_MESSAGE_TYPE",
            message=f"Unsupported notifications message type '{msg_type}'",
        )

    async def _mark_delivered(self, data: dict):
        """
        Placeholder delivery ACK.

        Keep this event for client compatibility until a real
        notification-delivery persistence flow is introduced.
        """
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
    async def handle_backend_event(self, event: dict):
        """
        Expected event shape:
            {
                "app": "notifications",
                "event": "...",
                "data": {...}
            }
        """
        event_type = event.get("event")
        data = event.get("data", {}) or {}

        logger.info(
            "[NotifHandler] handle_backend_event event_type=%s data=%s",
            event_type,
            data,
        )

        if not event_type:
            logger.warning("[NotifHandler] Missing backend event type")
            return

        await self._send_event(event_type, data)