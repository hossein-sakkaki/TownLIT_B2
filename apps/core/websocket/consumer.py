# apps/core/websocket/consumer.py

# ===================================================================
#                 CENTRAL WEBSOCKET GATEWAY
# ===================================================================

import json
import asyncio
import time
import logging
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth import get_user_model

# Registered handlers
from apps.core.websocket.handlers.presence import PresenceHandler
from apps.conversation.realtime.handler import ConversationHandler
from apps.notifications.realtime.handler import NotificationsHandler
from apps.posts.realtime.comments_handler import CommentsHandler
from apps.posts.realtime.reactions_handler import ReactionsHandler
from apps.sanctuary.realtime.handler import SanctuaryHandler
from apps.conversation.realtime.mixins.typing import (
    cancel_all_typing_timeouts_for_user,
)

# Central account gate
from apps.core.security.account_gate.constants import RESTRICTED_OWNER_CODE
from apps.core.security.account_gate.service import is_restricted_owner_user

logger = logging.getLogger(__name__)
User = get_user_model()


# ===================================================================
#   CENTRAL WEBSOCKET CONSUMER
# ===================================================================
class CentralWebSocketConsumer(AsyncJsonWebsocketConsumer):

    HEARTBEAT_INTERVAL = 20
    HEARTBEAT_TIMEOUT = 70

    # WebSocket close codes
    CLOSE_INVALID_PATH = 4404
    CLOSE_RESTRICTED_OWNER = 4409
    CLOSE_HEARTBEAT_TIMEOUT = 4000

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._processing_dispatch_event = False
        self._heartbeat_task = None
        self._last_pong_ts = time.time()
        self.connected = False
        self.handlers = {}
        self.feature_groups = set()
        self.device_id = None
        self.user = None

    # ---------------------------------------------------------------
    # CONNECT
    # ---------------------------------------------------------------
    async def connect(self):
        self.connected = False
        self.user = self.scope.get("user")

        # Path guard
        path = self.scope.get("path", "")
        if path not in ("/ws", "/ws/"):
            logger.warning("[WS BLOCKED] invalid path: %s", path)
            await self.close(code=self.CLOSE_INVALID_PATH)
            return

        # Reject anonymous users
        if not self.user or self.user.is_anonymous:
            logger.warning("[WS BLOCKED] anonymous user")
            await self.close(code=4401)
            return

        # Central restricted owner gate
        if await self._is_restricted_owner():
            logger.warning(
                "[WS BLOCKED] restricted owner user_id=%s code=%s",
                getattr(self.user, "id", None),
                RESTRICTED_OWNER_CODE,
            )
            await self.close(code=self.CLOSE_RESTRICTED_OWNER)
            return

        # Parse optional device_id
        qs = parse_qs(self.scope.get("query_string", b"").decode())
        device_id = (qs.get("device_id", [""])[0] or "").strip().lower()
        self.device_id = device_id if device_id else None

        # Register handlers only after passing all gates
        self._register_handlers()

        # Accept socket
        self.connected = True
        await self.accept()

        # Run handler connect hooks
        for name, handler in self.handlers.items():
            if hasattr(handler, "on_connect"):
                try:
                    await handler.on_connect()
                except Exception as e:
                    logger.error(
                        "[CENTRAL] handler '%s' on_connect error: %s",
                        name,
                        e,
                        exc_info=True,
                    )

        # Start heartbeat
        self._last_pong_ts = time.time()
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        # Send handshake
        await self.send_system(
            "connected",
            status="ok",
            user_id=self.user.id,
        )

    # ---------------------------------------------------------------
    # RESTRICTED OWNER GATE
    # ---------------------------------------------------------------
    async def _is_restricted_owner(self) -> bool:
        """
        Block WebSocket access for owner accounts whose own Member profile
        is temporarily unavailable.

        This prevents restricted users from joining:
        - presence
        - conversation
        - notifications
        - comments
        - reactions
        - sanctuary realtime groups
        """
        try:
            return await database_sync_to_async(is_restricted_owner_user)(
                self.user
            )
        except Exception as e:
            logger.error(
                "[CENTRAL] restricted owner check failed user_id=%s error=%s",
                getattr(self.user, "id", None),
                e,
                exc_info=True,
            )
            # Fail open to avoid accidental total lockout from transient DB errors.
            # HTTP middleware/view-level gates still protect API access.
            return False

    # ---------------------------------------------------------------
    # SAFE SEND
    # ---------------------------------------------------------------
    async def safe_send_json(self, data):
        if not getattr(self, "connected", False):
            return
        try:
            await self.send_json(data)
        except Exception:
            pass

    # ---------------------------------------------------------------
    # OUTBOUND HELPERS
    # ---------------------------------------------------------------
    async def send_system(self, msg_type: str, **fields):
        """
        Send gateway-level system message.
        Example:
            {"type": "connected", ...}
            {"type": "ping", ...}
            {"type": "error", ...}
        """
        payload = {"type": msg_type}
        payload.update(fields)
        await self.safe_send_json(payload)

    async def send_app_event(self, app: str, event: str, data: dict | None = None):
        """
        Send canonical app event envelope.
        """
        await self.safe_send_json({
            "type": "event",
            "app": app,
            "event": event,
            "data": data or {},
        })

    async def send_app_error(
        self,
        app: str,
        code: str,
        message: str,
        details: dict | None = None,
    ):
        """
        Send canonical app-level error.
        """
        data = {
            "code": code,
            "message": message,
        }
        if details:
            data["details"] = details

        await self.send_app_event(app=app, event="error", data=data)

    # ---------------------------------------------------------------
    # HANDLER REGISTRATION
    # ---------------------------------------------------------------
    def _register_handlers(self):
        self.handlers["presence"] = PresenceHandler(self)
        self.handlers["conversation"] = ConversationHandler(self)
        self.handlers["comments"] = CommentsHandler(self)
        self.handlers["reactions"] = ReactionsHandler(self)
        self.handlers["notifications"] = NotificationsHandler(self)
        self.handlers["sanctuary"] = SanctuaryHandler(self)

    # ---------------------------------------------------------------
    # HEARTBEAT
    # ---------------------------------------------------------------
    async def _heartbeat_loop(self):
        """
        Socket-level heartbeat.
        - server sends ping
        - client replies pong
        - timeout closes socket
        """
        try:
            while True:
                await self.send_system("ping", ts=int(time.time()))

                if (time.time() - self._last_pong_ts) > self.HEARTBEAT_TIMEOUT:
                    logger.warning("[CENTRAL] pong timeout -> closing socket")
                    try:
                        await self.close(code=self.CLOSE_HEARTBEAT_TIMEOUT)
                    except Exception:
                        pass
                    return

                await asyncio.sleep(self.HEARTBEAT_INTERVAL)

        except asyncio.CancelledError:
            return

    # ---------------------------------------------------------------
    # DISCONNECT
    # ---------------------------------------------------------------
    async def disconnect(self, close_code):
        self.connected = False

        # Cleanup typing timeouts
        if getattr(self, "user", None) and not self.user.is_anonymous:
            cancel_all_typing_timeouts_for_user(self.user.id)

        # Stop heartbeat
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

        # Leave all feature groups
        for group_name in list(self.feature_groups):
            try:
                await self.channel_layer.group_discard(group_name, self.channel_name)
            except Exception as e:
                logger.error("[CENTRAL] failed to leave %s: %s", group_name, e)

        self.feature_groups.clear()

        # Leave global user group
        try:
            if getattr(self, "user", None) and not self.user.is_anonymous:
                await self.channel_layer.group_discard(
                    f"user_{self.user.id}",
                    self.channel_name,
                )
        except Exception:
            pass

        # Let handlers cleanup internal state
        for handler in self.handlers.values():
            if hasattr(handler, "on_disconnect"):
                try:
                    await handler.on_disconnect()
                except Exception as e:
                    logger.error("[CENTRAL] handler cleanup error: %s", e)

    # ---------------------------------------------------------------
    # INBOUND NORMALIZATION
    # ---------------------------------------------------------------
    def _normalize_incoming_message(self, raw: dict) -> dict:
        """
        Canonical client -> server shape:
            {
                "app": str,
                "type": str,
                "data": {...}
            }

        Internal normalized shape:
            {
                "app": str | None,
                "type": str | None,
                "data": dict,
                ...flattened data fields
            }
        """
        app = raw.get("app")
        msg_type = raw.get("type")

        nested_data = raw.get("data")
        if not isinstance(nested_data, dict):
            nested_data = {}

        normalized = {
            "app": app,
            "type": msg_type,
            "data": nested_data,
        }

        # Flatten canonical data for handlers
        for k, v in nested_data.items():
            if k not in ("app", "type", "event", "data"):
                normalized[k] = v

        return normalized

    # ---------------------------------------------------------------
    # PONG HANDLER
    # ---------------------------------------------------------------
    async def _handle_pong(self):
        self._last_pong_ts = time.time()

        try:
            from apps.core.websocket.services.redis_online_manager import (
                refresh_user_connection,
            )

            if getattr(self, "user", None) and not self.user.is_anonymous:
                await refresh_user_connection(self.user.id, self.channel_name)

        except Exception as e:
            logger.error("[CENTRAL] refresh_user_connection failed: %s", e)

    # ---------------------------------------------------------------
    # RECEIVE -> ROUTE TO HANDLER
    # ---------------------------------------------------------------
    async def receive(self, text_data):
        try:
            raw = json.loads(text_data)
        except Exception:
            await self.send_system(
                "error",
                code="INVALID_JSON",
                message="Invalid JSON",
            )
            return

        if not isinstance(raw, dict):
            await self.send_system(
                "error",
                code="INVALID_MESSAGE",
                message="Message must be a JSON object",
            )
            return

        normalized = self._normalize_incoming_message(raw)

        app = normalized.get("app")
        msg_type = normalized.get("type")

        # Global socket-level pong
        if msg_type == "pong" and not app:
            await self._handle_pong()
            return

        if not app:
            await self.send_system(
                "error",
                code="MISSING_APP",
                message="Missing 'app' field",
            )
            return

        # Allow app-level pong too
        if msg_type == "pong":
            await self._handle_pong()
            return

        handler = self.handlers.get(app)
        if not handler:
            await self.send_system(
                "error",
                code="UNKNOWN_APP",
                message=f"No handler for app '{app}'",
            )
            return

        try:
            await handler.handle(normalized)
        except Exception as e:
            logger.error("[CENTRAL] Handler '%s' error: %s", app, e, exc_info=True)
            await self.send_app_error(
                app=app,
                code="HANDLER_FAILED",
                message="Handler failed",
            )

    # ---------------------------------------------------------------
    # UTILITIES FOR HANDLERS
    # ---------------------------------------------------------------
    async def join_feature_group(self, group_name: str):
        if not getattr(self, "connected", False):
            return
        await self.channel_layer.group_add(group_name, self.channel_name)
        self.feature_groups.add(group_name)

    async def leave_feature_group(self, group_name: str):
        if not getattr(self, "connected", False):
            return
        await self.channel_layer.group_discard(group_name, self.channel_name)
        self.feature_groups.discard(group_name)

    # ---------------------------------------------------------------
    # EVENT DISPATCHER
    # ---------------------------------------------------------------
    async def dispatch_event(self, event):
        """
        Unified backend -> WS dispatcher.
        Input shape expected from channel_layer.group_send:
            {
                "type": "dispatch_event",
                "app": "...",
                "event": "...",
                "data": {...}
            }
        """
        if getattr(self, "_processing_dispatch_event", False):
            logger.warning("[CENTRAL] Prevented recursive dispatch_event loop")
            return

        self._processing_dispatch_event = True

        try:
            app = event.get("app")
            evt = event.get("event")

            if not app or not evt:
                logger.error("[CENTRAL] dispatch_event missing app/event: %s", event)
                return

            handler = self.handlers.get(app)
            if not handler or not hasattr(handler, "handle_backend_event"):
                logger.error("[CENTRAL] No valid handler for app '%s'", app)
                return

            base = {
                k: v
                for k, v in event.items()
                if k not in ("type", "app", "event", "data")
            }

            inner = event.get("data") or {}
            if not isinstance(inner, dict):
                inner = {}

            base.update(inner)

            payload = {
                "app": app,
                "event": evt,
                "data": base,
            }

            if not getattr(self, "connected", False):
                return

            await handler.handle_backend_event(payload)

        except Exception as e:
            logger.error(
                "[CENTRAL] dispatch_event processing error: %s",
                e,
                exc_info=True,
            )

        finally:
            self._processing_dispatch_event = False