# apps/posts/consumers.py
from channels.generic.websocket import AsyncJsonWebsocketConsumer

class CommentsConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        # Accept immediately — JWTAuthMiddlewareStack already validated the user ✅
        self._groups = set()  # track joined groups per socket
        await self.accept()

    async def disconnect(self, close_code):
        # Leave all groups on disconnect ✅
        for g in list(self._groups):
            await self.channel_layer.group_discard(g, self.channel_name)
        self._groups.clear()

    async def receive_json(self, content, **kwargs):
        """
        Expected messages from client:
          - {type: "pong"}                          # keepalive
          - {type: "comments.subscribe", content_type_id: int, object_id: int}
          - {type: "comments.unsubscribe", content_type_id: int, object_id: int}
        """
        t = content.get("type")

        # --- ping/pong ---
        if t == "pong":
            return  # ignore keepalive ✅

        # --- subscribe ---
        if t == "comments.subscribe":
            ct_id = content.get("content_type_id")
            obj_id = content.get("object_id")
            if isinstance(ct_id, int) and isinstance(obj_id, int):
                g = f"comments.{ct_id}.{obj_id}"
                await self.channel_layer.group_add(g, self.channel_name)
                self._groups.add(g)
                # optional ack ✅
                await self.send_json({
                    "type": "comment.event",
                    "event": "subscribed",
                    "data": {"ct_id": ct_id, "object_id": obj_id},
                })
            return

        # --- unsubscribe ---
        if t == "comments.unsubscribe":
            ct_id = content.get("content_type_id")
            obj_id = content.get("object_id")
            if isinstance(ct_id, int) and isinstance(obj_id, int):
                g = f"comments.{ct_id}.{obj_id}"
                if g in self._groups:
                    await self.channel_layer.group_discard(g, self.channel_name)
                    self._groups.discard(g)
                    # optional ack ✅
                    await self.send_json({
                        "type": "comment.event",
                        "event": "unsubscribed",
                        "data": {"ct_id": ct_id, "object_id": obj_id},
                    })
            return

        # ignore unknown types ✅
        # await self.send_json({"type": "comment.event", "event": "ignored", "data": content})

    # ------------------------------------------------------------------
    # 🔥 Group messages (from backend via group_send)
    # ------------------------------------------------------------------
    async def comment_event(self, event):
        """
        event = {
            "type": "comment.event",
            "event": "created" | "updated" | "deleted",
            "data": {...}  # serialized CommentReadSerializer or {id: ...}
        }
        """
        kind = event.get("event")
        data = event.get("data", {})

        # optional: normalize event name for consistency
        if kind not in {"created", "updated", "deleted"}:
            kind = "unknown"

        # Send directly to browser ✅
        await self.send_json({
            "type": "comment.event",
            "event": kind,
            "data": data,
        })
