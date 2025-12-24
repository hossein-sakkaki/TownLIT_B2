# apps/posts/realtime/handler.py

from typing import Any, Dict
import logging

logger = logging.getLogger(__name__)


class CommentsHandler:
    """
    Enterprise-standard WS handler for comments.
    FE → BE payload shape:
        { app: "comments", type: "subscribe", payload: {...} }
    BE → FE events:
        { app: "comments", type: "event", event: "...", data: {...} }
    """

    def __init__(self, socket: Any) -> None:
        self.socket = socket
        self.user = getattr(socket, "user", None)
        self.groups: set[str] = set()

    # --------------------------------------------------------------
    async def on_connect(self) -> None:
        logger.info(f"[CommentsHandler] User {getattr(self.user, 'id', None)} connected")

    async def on_disconnect(self) -> None:
        for g in list(self.groups):
            try:
                await self.socket.leave_feature_group(g)
            except Exception as e:
                logger.error(f"[CommentsHandler] leave_feature_group({g}) failed: {e}")
        self.groups.clear()

        logger.info(f"[CommentsHandler] User {getattr(self.user, 'id', None)} disconnected")

    # --------------------------------------------------------------
    async def handle(self, data: Dict[str, Any]) -> None:
        msg_type = data.get("type")

        # ✅ Support BOTH shapes:
        # 1) {payload:{...}}
        # 2) payload merged into root by CentralConsumer.receive
        payload = data.get("payload")
        if not isinstance(payload, dict) or not payload:
            payload = {
                k: v
                for k, v in data.items()
                if k not in ("app", "type", "event", "data", "payload")
            }

        # --- keepalive ---
        if msg_type == "pong":
            return

        if msg_type == "subscribe":
            return await self._subscribe(payload)

        if msg_type == "unsubscribe":
            return await self._unsubscribe(payload)

        logger.debug(f"[CommentsHandler] Unknown msg type: {msg_type}")


    # --------------------------------------------------------------
    async def _subscribe(self, payload: Dict[str, Any]) -> None:
        ct_id = payload.get("content_type_id")
        obj_id = payload.get("object_id")

        if not isinstance(ct_id, int) or not isinstance(obj_id, int):
            logger.warning("[CommentsHandler] Invalid subscribe payload")
            return

        group = f"comments.{ct_id}.{obj_id}"

        await self.socket.join_feature_group(group)
        self.groups.add(group)

        await self.socket.send_json({
            "app": "comments",
            "type": "event",
            "event": "subscribed",
            "data": {"ct_id": ct_id, "object_id": obj_id},
        })

    # --------------------------------------------------------------
    async def _unsubscribe(self, payload: Dict[str, Any]) -> None:
        ct_id = payload.get("content_type_id")
        obj_id = payload.get("object_id")

        if not isinstance(ct_id, int) or not isinstance(obj_id, int):
            logger.warning("[CommentsHandler] Invalid unsubscribe payload")
            return

        group = f"comments.{ct_id}.{obj_id}"

        if group in self.groups:
            await self.socket.leave_feature_group(group)
            self.groups.discard(group)

            await self.socket.send_json({
                "app": "comments",
                "type": "event",
                "event": "unsubscribed",
                "data": {"ct_id": ct_id, "object_id": obj_id},
            })

    # --------------------------------------------------------------


    async def handle_backend_event(self, event: dict):
        kind = event.get("event")
        data = event.get("data")

        await self.socket.send_json({
            "app": "comments",
            "type": "event",
            "event": kind,
            "data": data,
        })
