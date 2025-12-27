# apps/core/websocket/consumer.py
# ===================================================================
#                 CENTRAL WEBSOCKET GATEWAY
# ===================================================================

import json
import asyncio
import time
import logging
from urllib.parse import parse_qs

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth import get_user_model

# Registered handlers
from apps.conversation.realtime.handler import ConversationHandler
from apps.notifications.realtime.handler import NotificationsHandler
from apps.posts.realtime.handler import CommentsHandler
from apps.sanctuary.realtime.handler import SanctuaryHandler
from apps.conversation.realtime.mixins.typing import TYPING_TIMEOUTS

logger = logging.getLogger(__name__)
User = get_user_model()


# ===================================================================
#   CENTRAL WEBSOCKET CONSUMER
# ===================================================================
class CentralWebSocketConsumer(AsyncJsonWebsocketConsumer):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._processing_dispatch_event = False

        self._heartbeat_task = None 
        self._last_pong_ts = time.time() 

    # ---------------------------------------------------------------
    # CONNECT
    # ---------------------------------------------------------------
    async def connect(self):
        self.connected = True
        self.user = self.scope.get("user")

        # --------------------------------------------------
        # 🛡️ PATH GUARD — block legacy WS endpoints
        # --------------------------------------------------
        path = self.scope.get("path", "")
        if path not in ("/ws", "/ws/"):
            logger.warning(f"[WS BLOCKED] invalid path: {path}")
            self.connected = False
            await self.close(code=4404)
            return
        
        # Reject anonymous users
        if not self.user or self.user.is_anonymous:
            self.connected = False
            await self.close()
            return

        # Parse optional device_id
        qs = parse_qs(self.scope.get("query_string", b"").decode())
        device_id = (qs.get("device_id", [""])[0] or "").strip().lower()
        self.device_id = device_id if device_id else None

        # Register handlers
        self.handlers = {}
        self.feature_groups = set()
        self._register_handlers()

        # ✅ Accept socket ONLY ONCE
        await self.accept()

        # Call on_connect() for handlers
        for name, handler in self.handlers.items():
            if hasattr(handler, "on_connect"):
                try:
                    await handler.on_connect()
                except Exception as e:
                    logger.error(
                        f"[CENTRAL] handler '{name}' on_connect error: {e}",
                        exc_info=True,
                    )

        # Start heartbeat (socket-level)
        self._last_pong_ts = time.time()
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        # Send handshake
        await self.safe_send_json({
            "type": "connected",
            "status": "ok",
            "user_id": self.user.id,
        })


    # ---------------------------------------------------------------
    # SAFE SEND (ASGI-SAFE)
    # ---------------------------------------------------------------
    async def safe_send_json(self, data):
        if not getattr(self, "connected", False):
            return
        try:
            await self.send_json(data)
        except Exception:
            # Socket already closed → silently ignore
            pass


    # ---------------------------------------------------------------
    # HANDLER REGISTRATION
    # ---------------------------------------------------------------
    def _register_handlers(self):
        """
        ONLY register and instantiate handlers.
        No logic or group join should be done here.
        """
        # You may add more handlers later:
        self.handlers["conversation"] = ConversationHandler(self)
        self.handlers["comments"] = CommentsHandler(self)
        self.handlers["notifications"] = NotificationsHandler(self)
        self.handlers["sanctuary"] = SanctuaryHandler(self)


    # ---------------------------------------------------------------
    # HEARTBEAT
    # ---------------------------------------------------------------
    async def _heartbeat_loop(self):
        """
        Socket-level heartbeat:
        - send ping every 20s
        - if no pong for >70s, close socket to trigger cleanup
        """
        try:
            while True:
                # Send ping
                try:
                    await self.safe_send_json({"type": "ping", "ts": int(time.time())})
                except Exception:
                    return  # socket closed

                # Watchdog timeout
                if (time.time() - self._last_pong_ts) > 70:
                    logger.warning("[CENTRAL] pong timeout -> closing socket")
                    try:
                        await self.close(code=4000)
                    except Exception:
                        pass
                    return

                await asyncio.sleep(20)  # < Redis TTL (60s)
        except asyncio.CancelledError:
            return


    # ---------------------------------------------------------------
    # DISCONNECT
    # ---------------------------------------------------------------
    async def disconnect(self, close_code):
        self.connected = False

        # --------------------------------------------------
        # CLEANUP TYPING TIMEOUTS FOR THIS USER (CRITICAL)
        # --------------------------------------------------
        if getattr(self, "user", None):
            for key in list(TYPING_TIMEOUTS.keys()):
                uid = key
                if uid == self.user.id:
                    try:
                        TYPING_TIMEOUTS[uid].cancel()
                    except Exception:
                        pass
                    del TYPING_TIMEOUTS[uid]


        # --------------------------------------------------
        # Stop heartbeat
        # --------------------------------------------------
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

        # Leave all handler-level groups
        for group_name in list(self.feature_groups):
            try:
                await self.channel_layer.group_discard(group_name, self.channel_name)
            except Exception as e:
                logger.error(f"[CENTRAL] failed to leave {group_name}: {e}")

        self.feature_groups.clear()

        # Leave global user group
        try:
            await self.channel_layer.group_discard(f"user_{self.user.id}", self.channel_name)
        except:
            pass

        # Let handlers clean their internal state
        for h in self.handlers.values():
            if hasattr(h, "on_disconnect"):
                try:
                    await h.on_disconnect()
                except Exception as e:
                    logger.error(f"[CENTRAL] handler cleanup error: {e}")

    # ---------------------------------------------------------------
    # RECEIVE → ROUTE TO HANDLER
    # ---------------------------------------------------------------
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except Exception:
            await self.safe_send_json({"type": "error", "message": "Invalid JSON"})
            return

        # Normalize unified envelope: merge payload into root
        if isinstance(data, dict) and "payload" in data and isinstance(data["payload"], dict):
            payload = data.pop("payload")
            for k, v in payload.items():
                # Do not override reserved keys
                if k not in ("app", "type"):
                    data[k] = v

        app = data.get("app")
        msg_type = data.get("type")

        # GLOBAL: refresh Redis TTL on pong (no app required)
        if msg_type == "pong":
            self._last_pong_ts = time.time()
            try:
                from services.redis_online_manager import refresh_user_connection
                if getattr(self, "user", None) and not self.user.is_anonymous:
                    await refresh_user_connection(self.user.id, self.channel_name)
            except Exception as e:
                logger.error(f"[CENTRAL] refresh_user_connection failed: {e}")
            return

        if not app:
            await self.safe_send_json({"type": "error", "message": "Missing 'app' field"})
            return

        handler = self.handlers.get(app)
        if not handler:
            await self.safe_send_json({"type": "error", "message": f"No handler for app '{app}'"})
            return

        try:
            await handler.handle(data)
        except Exception as e:
            logger.error(f"[CENTRAL] Handler '{app}' error: {e}", exc_info=True)
            await self.safe_send_json({"type": "error", "message": "Handler failed"})



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
        Unified backend → WS dispatcher.
        Expected event structure (new style):

        {
            "type": "dispatch_event",
            "app": "conversation" | "notifications" | "comments" | ...,
            "event": "chat_message" | "mark_as_read" | "typing_status_broadcast" | ...,
            "data": {...}   # preferred place for payload
        }

        But we also support legacy extra keys at top-level:
        {
            "type": "dispatch_event",
            "app": "conversation",
            "event": "typing_status_broadcast",
            "dialogue_slug": "...",
            "sender": {...},
            "is_typing": true
        }
        """

        # --------- Safety Guard: Prevent backend recursion ----------
        if getattr(self, "_processing_dispatch_event", False):
            # A backend event triggered another backend event → ignore
            logger.warning("[CENTRAL] Prevented recursive dispatch_event loop")
            return

        self._processing_dispatch_event = True
        try:
            app = event.get("app")
            evt = event.get("event")

            if not app or not evt:
                logger.error(f"[CENTRAL] dispatch_event missing app/event: {event}")
                return

            handler = self.handlers.get(app)
            if not handler or not hasattr(handler, "handle_backend_event"):
                logger.error(f"[CENTRAL] No valid handler for app '{app}'")
                return

            # ---------- Merge legacy top-level keys into data ----------
            # 1) Take all non-reserved keys at top-level
            base = {
                k: v
                for k, v in event.items()
                if k not in ("type", "app", "event", "data")
            }

            # 2) Overlay with inner "data" dict if present
            inner = event.get("data") or {}
            if not isinstance(inner, dict):
                inner = {}

            base.update(inner)  # inner "data" wins on conflict

            payload = {
                "app": app,
                "event": evt,
                "data": base,
            }

            # Forward merged payload to handler
            if not getattr(self, "connected", False):
                return

            await handler.handle_backend_event(payload)

        except Exception as e:
            logger.error(
                f"[CENTRAL] dispatch_event processing error: {e}",
                exc_info=True,
            )

        finally:
            self._processing_dispatch_event = False
