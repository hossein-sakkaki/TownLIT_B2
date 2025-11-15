# apps/notifications/consumers.py
import logging
from channels.generic.websocket import AsyncJsonWebsocketConsumer

logger = logging.getLogger(__name__)


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        """Private WS channel for real-time notifications."""
        user = self.scope.get("user")

        # Reject anonymous users
        if not user or user.is_anonymous:
            logger.warning("[WS-Notif] Anonymous connection attempt rejected.")
            await self.close()
            return

        self.user = user

        # ✅ FIX: Use a dedicated group only for notifications
        self.group_name = f"notif_user_{user.id}"

        # Join notification-only channel
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        logger.debug(f"[WS-Notif] Connected: user={user.username} → group={self.group_name}")

        # Confirm connection
        await self.send_json({"type": "connected", "status": "ok"})

    async def disconnect(self, close_code):
        """Remove user from WS group when socket closes."""
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            logger.debug(f"[WS-Notif] Disconnected user={getattr(self, 'user', None)}")

    # ------------------------------------------------------------------
    # Client → Server
    # ------------------------------------------------------------------
    async def receive_json(self, content, **kwargs):
        """Handle ping / delivered events."""
        msg_type = content.get("type")

        if msg_type == "ping":
            await self.ping()
        elif msg_type == "delivered":
            await self.mark_as_delivered()
        else:
            logger.debug(f"[WS-Notif] Unknown message type: {msg_type}")

    async def ping(self):
        """Heartbeat response."""
        await self.send_json({"type": "pong"})
        logger.debug(f"[WS-Notif] Pong → {self.user.username}")

    async def mark_as_delivered(self):
        """Client acknowledges receiving the notification."""
        await self.send_json({"type": "ack", "status": "ok"})
        logger.debug(f"[WS-Notif] Delivery ACK ← user {self.user.id}")

    # ------------------------------------------------------------------
    # Server → Client
    # ------------------------------------------------------------------
    async def send_notification(self, event):
        """
        Called from group_send(type="send_notification")
        """
        try:
            payload = event.get("payload", {})
            await self.send_json({
                "type": "notification",
                "payload": payload,
            })
            logger.debug(f"[WS-Notif] Sent → {self.user.username}: {payload}")
        except Exception as e:
            logger.error(f"[WS-Notif] Failed to send notification: {e}")
