import json
from channels.generic.websocket import AsyncWebsocketConsumer

# Real-time notifications ---------------------------------------------------
class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Each user joins a private WS group
        user = self.scope.get("user")
        if not user or user.is_anonymous:
            await self.close()
            return

        self.user = user
        self.group_name = f"user_{user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        # Remove user from their WS group
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        """
        Optional: handle client pings or mark-read requests.
        """
        try:
            data = json.loads(text_data)
            action = data.get("action")
            # Simple ping test
            if action == "ping":
                await self.send_json({"type": "pong"})
        except Exception:
            pass

    async def send_notification(self, event):
        """
        Called by group_send() when a new notification is dispatched.
        """
        payload = event.get("payload", {})
        await self.send(text_data=json.dumps({
            "type": "notification",
            "payload": payload,
        }))
