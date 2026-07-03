# apps/posts/realtime/comments_handler.py

from typing import Any, Dict
import logging

from channels.db import database_sync_to_async
from django.contrib.contenttypes.models import ContentType

logger = logging.getLogger(__name__)


class CommentsHandler:
    """
    Canonical WS handler for comments.

    Client -> Server:
        {
            "app": "comments",
            "type": "subscribe",
            "data": {
                "content_type_id": 23,      # legacy/numeric
                "content_type": "posts.moment",
                "object_id": 42
            }
        }

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

    @database_sync_to_async
    def _resolve_content_type_id(self, value: Any) -> int | None:
        if value is None:
            return None

        raw = str(value).strip().lower()

        if not raw:
            return None

        try:
            if raw.isdigit():
                return ContentType.objects.get(pk=int(raw)).id

            if "." in raw:
                app_label, model = raw.split(".", 1)
                return ContentType.objects.get(
                    app_label=app_label,
                    model=model,
                ).id

            return ContentType.objects.get(model=raw).id

        except ContentType.DoesNotExist:
            return None

    async def _resolve_subscription_target(
        self,
        data: Dict[str, Any],
    ) -> tuple[int | None, str | None, int | None]:
        object_id = self._to_int(data.get("object_id"))

        content_type_id = (
            self._to_int(data.get("content_type_id"))
            or self._to_int(data.get("ct_id"))
        )

        content_type = data.get("content_type")

        if not content_type_id and content_type:
            content_type_id = await self._resolve_content_type_id(content_type)

        normalized_content_type = (
            str(content_type).strip().lower()
            if content_type is not None and str(content_type).strip()
            else None
        )

        return content_type_id, normalized_content_type, object_id

    # --------------------------------------------------------------
    async def on_connect(self) -> None:
        logger.info(
            "[CommentsHandler] User %s connected",
            getattr(self.user, "id", None),
        )

    async def on_disconnect(self) -> None:
        for group_name in list(self.groups):
            try:
                await self.socket.leave_feature_group(group_name)
            except Exception as e:
                logger.error(
                    "[CommentsHandler] leave_feature_group(%s) failed: %s",
                    group_name,
                    e,
                    exc_info=True,
                )

        self.groups.clear()

        logger.info(
            "[CommentsHandler] User %s disconnected",
            getattr(self.user, "id", None),
        )

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
        ct_id, content_type, obj_id = await self._resolve_subscription_target(data)

        if not ct_id or not obj_id:
            await self._send_error(
                code="INVALID_SUBSCRIBE_PAYLOAD",
                message="content_type_id or content_type, and object_id are required",
            )
            return

        group = f"comments.{ct_id}.{obj_id}"

        await self.socket.join_feature_group(group)
        self.groups.add(group)

        await self._send_event(
            "subscribed",
            {
                "ct_id": ct_id,
                "content_type_id": ct_id,
                "content_type": content_type,
                "object_id": obj_id,
            },
        )

    # --------------------------------------------------------------
    async def _unsubscribe(self, data: Dict[str, Any]) -> None:
        ct_id, content_type, obj_id = await self._resolve_subscription_target(data)

        if not ct_id or not obj_id:
            await self._send_error(
                code="INVALID_UNSUBSCRIBE_PAYLOAD",
                message="content_type_id or content_type, and object_id are required",
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
                "content_type_id": ct_id,
                "content_type": content_type,
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