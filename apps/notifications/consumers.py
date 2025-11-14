import logging
from channels.generic.websocket import AsyncJsonWebsocketConsumer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Real-time notifications (single private channel per user)
# ---------------------------------------------------------------------------
class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        """Establish a private WS channel for each authenticated user."""
        user = self.scope.get("user")

        # Reject anonymous users
        if not user or user.is_anonymous:
            logger.warning("[WS-Notif] Anonymous connection attempt rejected.")
            await self.close()
            return

        self.user = user
        self.group_name = f"user_{user.id}"

        # Join user's private group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.debug(f"[WS-Notif] Connected: user={user.username} → group={self.group_name}")

        # Confirm connection
        await self.send_json({"type": "connected", "status": "ok"})

    async def disconnect(self, close_code):
        """Remove user from WS group when socket closes."""
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            logger.debug(f"[WS-Notif] Disconnected: user={getattr(self, 'user', None)}")

    # ------------------------------------------------------------------
    # Client → Server messages
    # ------------------------------------------------------------------
    async def receive_json(self, content, **kwargs):
        """Handle incoming messages (ping / delivered)."""
        msg_type = content.get("type")

        if msg_type == "ping":
            await self.ping(content)
        elif msg_type == "delivered":
            await self.mark_as_delivered(content)
        else:
            logger.debug(f"[WS-Notif] Unknown message type: {msg_type}")

    async def ping(self, event):
        """Respond to heartbeat ping from frontend."""
        await self.send_json({"type": "pong"})
        logger.debug(f"[WS-Notif] Pong sent → {self.user.username}")

    async def mark_as_delivered(self, event):
        """Client confirms receipt of notification."""
        user_id = getattr(self.user, "id", None)
        await self.send_json({"type": "ack", "status": "ok"})
        logger.debug(f"[WS-Notif] Delivery ACK from user {user_id}")

    # ------------------------------------------------------------------
    # Server → Client messages
    # ------------------------------------------------------------------
    async def send_notification(self, event):
        """
        Called via group_send(type='send_notification') when a new notification is created.
        Expects: {'type': 'send_notification', 'payload': {...}}
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
