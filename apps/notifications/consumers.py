# apps/notifications/consumers.py

import logging
from channels.generic.websocket import AsyncJsonWebsocketConsumer

logger = logging.getLogger(__name__)


class NotificationConsumer(AsyncJsonWebsocketConsumer):

    async def connect(self):
        """
        Private WebSocket for user notification stream.
        Clean version without noisy print() logs.
        """

        user = self.scope.get("user")

        if not user or user.is_anonymous:
            logger.warning("[WS-Notif] Anonymous user attempted to connect")
            await self.close()
            return

        self.user = user
        self.group_name = f"notif_user_{user.id}"

        # Join private notification group
        try:
            await self.channel_layer.group_add(self.group_name, self.channel_name)
        except Exception as e:
            logger.error(f"[WS-Notif] Failed to join group {self.group_name}: {e}")

        await self.accept()

        # Optional handshake
        await self.send_json({"type": "connected", "status": "ok"})

        logger.info(f"[WS-Notif] User {user.id} connected to WS notifications")


    async def disconnect(self, close_code):
        """
        Remove user from the group when socket closes.
        """
        if hasattr(self, "group_name"):
            try:
                await self.channel_layer.group_discard(self.group_name, self.channel_name)
            except Exception as e:
                logger.error(f"[WS-Notif] Failed group_discard({self.group_name}): {e}")

        logger.info(f"[WS-Notif] User {getattr(self.user, 'id', None)} disconnected")


    async def receive_json(self, content, **kwargs):
        """
        Handle messages received from client.
        """

        msg_type = content.get("type")

        if msg_type == "ping":
            await self.ping()

        elif msg_type == "pong":
            # Lightweight – no log needed
            pass

        elif msg_type == "delivered":
            await self.mark_as_delivered()

        else:
            logger.debug(f"[WS-Notif] Unknown message type received: {msg_type}")


    async def ping(self):
        await self.send_json({"type": "pong"})

    async def mark_as_delivered(self):
        await self.send_json({"type": "ack", "status": "ok"})


    # ------------------------------------------------------------------
    # Server → Client Delivery
    # ------------------------------------------------------------------

    async def send_notification(self, event):
        """
        Handler for group_send(type="send_notification")
        """

        try:
            payload = event.get("payload", {})

            await self.send_json({
                "type": "notification",
                "payload": payload,
            })

        except Exception as e:
            logger.error(f"[WS-Notif] Error sending WS notif to user {self.user.id}: {e}")
