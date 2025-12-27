# apps/notifications/realtime/handler.py
import logging

logger = logging.getLogger(__name__)


class NotificationsHandler:
    """
    Unified WS handler for notifications.
    FE → BE:
        { app: "notifications", type: "ping" }
        { app: "notifications", type: "delivered", payload: {...} }

    BE → FE (through dispatch_event):
        {
            "app": "notifications",
            "event": "notification",
            "data": {...}
        }
    """

    def __init__(self, socket):
        self.socket = socket
        self.user = socket.user
        self.group = f"notif_user_{self.user.id}"

    # ------------------------------------------------------
    async def on_connect(self):
        try:
            await self.socket.join_feature_group(self.group)
        except Exception as e:
            logger.error(f"[NotifHandler] join {self.group} failed: {e}")

        await self.socket.safe_send_json({
            "app": "notifications",
            "type": "connected",
            "status": "ok"
        })

    # ------------------------------------------------------
    async def on_disconnect(self):
        try:
            await self.socket.leave_feature_group(self.group)
        except Exception as e:
            logger.error(f"[NotifHandler] leave {self.group} failed: {e}")

    # ------------------------------------------------------
    async def handle(self, data):
        msg_type = data.get("type")

        if msg_type == "pong":
            return

        if msg_type == "ping":
            return await self._ping()

        if msg_type == "delivered":
            return await self._mark_delivered(data.get("payload"))

        logger.debug(f"[NotifHandler] Unknown event: {msg_type}")

    # ------------------------------------------------------
    async def _ping(self):
        await self.socket.safe_send_json({
            "app": "notifications",
            "type": "pong"
        })

    async def _mark_delivered(self, payload):
        await self.socket.safe_send_json({
            "app": "notifications",
            "type": "ack",
            "status": "ok"
        })

    # ------------------------------------------------------
    # BACKEND → FE (called by CentralConsumer.dispatch_event)
    # ------------------------------------------------------
    async def handle_backend_event(self, event):
        """
        event = {
            "app": "notifications",
            "event": "notification",
            "data": {...}
        }
        """

        event_type = event.get("event")
        data = event.get("data", {})

        logger.info(
            "[NotifHandler] handle_backend_event called: event_type=%s data=%s",
            event_type,
            data,
        )

        await self.socket.safe_send_json({
            "app": "notifications",
            "type": "event",
            "event": event_type,
            "data": data,
        })

        logger.info("[NotifHandler] JSON sent to client")