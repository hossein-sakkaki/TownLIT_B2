# apps/posts/realtime/comments_handler.py

from typing import Any, Dict
import logging

logger = logging.getLogger(__name__)


class CommentsHandler:
    """
    Canonical WS handler for comments.

    Client -> Server:
        { "app": "comments", "type": "subscribe", "data": {...} }
        { "app": "comments", "type": "unsubscribe", "data": {...} }

    Server -> Client:
        { "app": "comments", "type": "event", "event": "...", "data": {...} }
    """

    APP = "comments"

    def __init__(self, socket: Any) -> None:
        self.socket = socket
        self.user = getattr(socket, "user", None)
        self.groups: set[str] = set()

    # --------------------------------------------------------------
    # Helpers
    # --------------------------------------------------------------
    def _message_data(self, message: Dict[str, Any]) -> Dict[str, Any]:
        data = message.get("data")
        if isinstance(data, dict):
            return data
        return {}

    async def _send_event(self, event: str, data: Dict[str, Any] | None = None) -> None:
        await self.socket.send_app_event(
            app=self.APP,
            event=event,
            data=data or {},
        )

    async def _send_error(
        self,
        code: str,
        message: str,
        details: Dict[str, Any] | None = None,
    ) -> None:
        await self.socket.send_app_error(
            app=self.APP,
            code=code,
            message=message,
            details=details,
        )

    @staticmethod
    def _to_int(value) -> int | None:
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return None
        return None

    # --------------------------------------------------------------
    async def on_connect(self) -> None:
        logger.info(f"[CommentsHandler] User {getattr(self.user, 'id', None)} connected")

    async def on_disconnect(self) -> None:
        for group_name in list(self.groups):
            try:
                await self.socket.leave_feature_group(group_name)
            except Exception as e:
                logger.error(
                    f"[CommentsHandler] leave_feature_group({group_name}) failed: {e}",
                    exc_info=True,
                )

        self.groups.clear()
        logger.info(f"[CommentsHandler] User {getattr(self.user, 'id', None)} disconnected")

    # --------------------------------------------------------------
    async def handle(self, message: Dict[str, Any]) -> None:
        msg_type = message.get("type")
        data = self._message_data(message)

        if msg_type == "subscribe":
            await self._subscribe(data)
            return

        if msg_type == "unsubscribe":
            await self._unsubscribe(data)
            return

        await self._send_error(
            code="UNSUPPORTED_MESSAGE_TYPE",
            message=f"Unsupported comments message type '{msg_type}'",
        )

    # --------------------------------------------------------------
    async def _subscribe(self, data: Dict[str, Any]) -> None:
        ct_id = self._to_int(data.get("content_type_id"))
        obj_id = self._to_int(data.get("object_id"))

        if not ct_id or not obj_id:
            await self._send_error(
                code="INVALID_SUBSCRIBE_PAYLOAD",
                message="content_type_id and object_id are required",
            )
            return

        group = f"comments.{ct_id}.{obj_id}"

        await self.socket.join_feature_group(group)
        self.groups.add(group)

        await self._send_event(
            "subscribed",
            {
                "ct_id": ct_id,
                "object_id": obj_id,
            },
        )

    # --------------------------------------------------------------
    async def _unsubscribe(self, data: Dict[str, Any]) -> None:
        ct_id = self._to_int(data.get("content_type_id"))
        obj_id = self._to_int(data.get("object_id"))

        if not ct_id or not obj_id:
            await self._send_error(
                code="INVALID_UNSUBSCRIBE_PAYLOAD",
                message="content_type_id and object_id are required",
            )
            return

        group = f"comments.{ct_id}.{obj_id}"

        if group in self.groups:
            await self.socket.leave_feature_group(group)
            self.groups.discard(group)

        await self._send_event(
            "unsubscribed",
            {
                "ct_id": ct_id,
                "object_id": obj_id,
            },
        )

    # --------------------------------------------------------------
    async def handle_backend_event(self, event: dict):
        event_type = event.get("event")
        data = event.get("data", {}) or {}

        if not event_type:
            logger.warning("[CommentsHandler] Missing backend event type")
            return

        await self._send_event(event_type, data)