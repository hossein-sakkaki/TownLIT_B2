# apps/posts/realtime/reactions_handler.py

from typing import Any, Dict, Optional
import logging

from channels.db import database_sync_to_async
from django.contrib.contenttypes.models import ContentType

logger = logging.getLogger(__name__)


class ReactionsHandler:
    """
    Canonical WS handler for reactions.

    Client -> Server:
      { "app": "reactions", "type": "subscribe_target", "data": {...} }
      { "app": "reactions", "type": "unsubscribe_target", "data": {...} }

      { "app": "reactions", "type": "subscribe_inbox", "data": {...} }
      { "app": "reactions", "type": "unsubscribe_inbox", "data": {...} }

    Supports both:
      - content_type_id + object_id
      - content_type + object_id

    Server -> Client:
      { "app": "reactions", "type": "event", "event": "...", "data": {...} }
    """

    APP = "reactions"

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

    def _target_group(self, ct_id: int, obj_id: int) -> str:
        return f"reactions.target.{ct_id}.{obj_id}"

    def _inbox_group(self, ct_id: int, obj_id: int, user_id: int) -> str:
        return f"reactions.inbox.{ct_id}.{obj_id}.{user_id}"

    async def _resolve_payload_content_type(
        self,
        data: Dict[str, Any],
    ) -> ContentType | None:
        ct_id = self._to_int(data.get("content_type_id"))
        if ct_id:
            return await self._get_content_type_by_id(ct_id)

        raw = data.get("content_type")
        if not raw:
            return None

        return await self._get_content_type_by_value(str(raw))

    # --------------------------------------------------------------
    async def on_connect(self) -> None:
        logger.info(f"[ReactionsHandler] User {getattr(self.user, 'id', None)} connected")

    async def on_disconnect(self) -> None:
        for group_name in list(self.groups):
            try:
                await self.socket.leave_feature_group(group_name)
            except Exception as e:
                logger.error(
                    f"[ReactionsHandler] leave_feature_group({group_name}) failed: {e}",
                    exc_info=True,
                )

        self.groups.clear()
        logger.info(f"[ReactionsHandler] User {getattr(self.user, 'id', None)} disconnected")

    # --------------------------------------------------------------
    async def handle(self, message: Dict[str, Any]) -> None:
        msg_type = message.get("type")
        data = self._message_data(message)

        if msg_type == "subscribe_target":
            await self._subscribe_target(data)
            return

        if msg_type == "unsubscribe_target":
            await self._unsubscribe_target(data)
            return

        if msg_type == "subscribe_inbox":
            await self._subscribe_inbox(data)
            return

        if msg_type == "unsubscribe_inbox":
            await self._unsubscribe_inbox(data)
            return

        await self._send_error(
            code="UNSUPPORTED_MESSAGE_TYPE",
            message=f"Unsupported reactions message type '{msg_type}'",
        )

    # --------------------------------------------------------------
    async def _subscribe_target(self, data: Dict[str, Any]) -> None:
        cto = await self._resolve_payload_content_type(data)
        obj_id = self._to_int(data.get("object_id"))

        if not cto or not obj_id:
            await self._send_error(
                code="INVALID_SUBSCRIBE_TARGET_PAYLOAD",
                message="content_type/content_type_id and object_id are required",
            )
            return

        group = self._target_group(cto.id, obj_id)

        await self.socket.join_feature_group(group)
        self.groups.add(group)

        await self._send_event(
            "subscribed_target",
            {
                "content_type_id": cto.id,
                "content_type": f"{cto.app_label}.{cto.model}",
                "object_id": obj_id,
            },
        )

    async def _unsubscribe_target(self, data: Dict[str, Any]) -> None:
        cto = await self._resolve_payload_content_type(data)
        obj_id = self._to_int(data.get("object_id"))

        if not cto or not obj_id:
            await self._send_error(
                code="INVALID_UNSUBSCRIBE_TARGET_PAYLOAD",
                message="content_type/content_type_id and object_id are required",
            )
            return

        group = self._target_group(cto.id, obj_id)

        if group in self.groups:
            await self.socket.leave_feature_group(group)
            self.groups.discard(group)

        await self._send_event(
            "unsubscribed_target",
            {
                "content_type_id": cto.id,
                "content_type": f"{cto.app_label}.{cto.model}",
                "object_id": obj_id,
            },
        )

    async def _subscribe_inbox(self, data: Dict[str, Any]) -> None:
        cto = await self._resolve_payload_content_type(data)
        obj_id = self._to_int(data.get("object_id"))

        if not cto or not obj_id:
            await self._send_error(
                code="INVALID_SUBSCRIBE_INBOX_PAYLOAD",
                message="content_type/content_type_id and object_id are required",
            )
            return

        is_owner = await self._is_owner(cto.id, obj_id, getattr(self.user, "id", None))
        if not is_owner:
            await self._send_error(
                code="FORBIDDEN",
                message="Forbidden",
            )
            return

        group = self._inbox_group(cto.id, obj_id, self.user.id)

        await self.socket.join_feature_group(group)
        self.groups.add(group)

        await self._send_event(
            "subscribed_inbox",
            {
                "content_type_id": cto.id,
                "content_type": f"{cto.app_label}.{cto.model}",
                "object_id": obj_id,
            },
        )

    async def _unsubscribe_inbox(self, data: Dict[str, Any]) -> None:
        cto = await self._resolve_payload_content_type(data)
        obj_id = self._to_int(data.get("object_id"))

        if not cto or not obj_id:
            await self._send_error(
                code="INVALID_UNSUBSCRIBE_INBOX_PAYLOAD",
                message="content_type/content_type_id and object_id are required",
            )
            return

        group = self._inbox_group(cto.id, obj_id, getattr(self.user, "id", 0))

        if group in self.groups:
            await self.socket.leave_feature_group(group)
            self.groups.discard(group)

        await self._send_event(
            "unsubscribed_inbox",
            {
                "content_type_id": cto.id,
                "content_type": f"{cto.app_label}.{cto.model}",
                "object_id": obj_id,
            },
        )

    # --------------------------------------------------------------
    async def handle_backend_event(self, event: dict):
        event_type = event.get("event")
        data = event.get("data", {}) or {}

        if not event_type:
            logger.warning("[ReactionsHandler] Missing backend event type")
            return

        await self._send_event(event_type, data)

    # --------------------------------------------------------------
    @database_sync_to_async
    def _get_content_type_by_id(self, ct_id: int) -> ContentType | None:
        try:
            return ContentType.objects.get(pk=ct_id)
        except ContentType.DoesNotExist:
            return None

    @database_sync_to_async
    def _get_content_type_by_value(self, raw_value: str) -> ContentType | None:
        raw = str(raw_value or "").strip().lower()

        if not raw:
            return None

        alias_map = {
            "moment": ("posts", "moment"),
            "testimony": ("posts", "testimony"),
            "prayer": ("posts", "prayer"),
            "pray": ("posts", "prayer"),
            "prayerresponse": ("posts", "prayer"),
            "prayer_response": ("posts", "prayer"),
            "prayer-response": ("posts", "prayer"),
        }

        try:
            if raw.isdigit():
                return ContentType.objects.get(pk=int(raw))

            if "." in raw:
                app_label, model = raw.split(".", 1)
                app_label = app_label.strip()
                model = model.strip()

                if app_label == "posts" and model in alias_map:
                    target = alias_map[model]
                    return ContentType.objects.get(app_label=target[0], model=target[1])

                return ContentType.objects.get(app_label=app_label, model=model)

            if raw in alias_map:
                target = alias_map[raw]
                return ContentType.objects.get(app_label=target[0], model=target[1])

            matches = ContentType.objects.filter(model=raw)
            if matches.count() == 1:
                return matches.first()

            return None
        except ContentType.DoesNotExist:
            return None

    @database_sync_to_async
    def _is_owner(self, ct_id: int, obj_id: int, user_id: Optional[int]) -> bool:
        if not user_id:
            return False

        try:
            cto = ContentType.objects.get(pk=ct_id)
        except ContentType.DoesNotExist:
            return False

        model_cls = cto.model_class()
        if model_cls is None:
            return False

        try:
            target_obj = model_cls._default_manager.get(pk=obj_id)
        except model_cls.DoesNotExist:
            return False

        return self._resolve_owner_user_id(target_obj) == user_id

    def _resolve_owner_user_id(self, obj):
        base = obj

        if hasattr(base, "content_object") and getattr(base, "content_object") is not None:
            base = base.content_object

        for fk in ("user_id", "name_id", "owner_id", "member_user_id", "org_owner_user_id"):
            if hasattr(base, fk):
                val = getattr(base, fk)
                if isinstance(val, int):
                    return val

        if base.__class__.__name__.lower() == "member" and hasattr(base, "user_id"):
            return getattr(base, "user_id", None)

        for rel in ("name", "owner", "member_user", "org_owner_user"):
            if hasattr(base, rel):
                rel_obj = getattr(base, rel)
                if getattr(rel_obj, "id", None):
                    return rel_obj.id

        return None