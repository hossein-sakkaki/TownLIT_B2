# apps/core/websocket/consumer_v2.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-23.
# Last Update by Hossein Sakkaki on 2026-11-02.

import asyncio
import json
import logging
import re
import time

from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

from django.conf import settings

from apps.core.websocket.access_auth import (
    authenticate_websocket_access_token,
    check_websocket_session_access,
)
from apps.core.websocket.consumer import CentralWebSocketConsumer


logger = logging.getLogger(__name__)


class CentralWebSocketConsumerV2(CentralWebSocketConsumer):
    AUTH_TIMEOUT_SECONDS = 10
    MAX_AUTH_MESSAGE_BYTES = 16384
    MAX_APPLICATION_MESSAGE_BYTES = 1048576
    SESSION_ACCESS_CHECK_SECONDS = 30

    CLOSE_UNAUTHORIZED = 4401
    CLOSE_INVALID_AUTH = 4400
    CLOSE_ORIGIN_DENIED = 4403
    CLOSE_AUTH_TIMEOUT = 4408
    CLOSE_DEVICE_REVOKED = 4406

    async def connect(self):
        self.connected = False
        self.user = None
        self._v2_authenticated = False
        self._v2_open = False
        self._v2_auth_timer = None
        self._v2_expiry_task = None
        self._v2_access_monitor = None
        self._v2_close_requested = False
        self._v2_expires_at = 0

        if self.scope.get("path") not in ("/ws/v2", "/ws/v2/"):
            await self.close(code=self.CLOSE_INVALID_PATH)
            return

        if self.scope.get("query_string", b""):
            await self.close(code=self.CLOSE_INVALID_AUTH)
            return

        if not self._origin_allowed():
            logger.warning("[WS V2] Origin rejected")
            await self.close(code=self.CLOSE_ORIGIN_DENIED)
            return

        await self.accept()
        self._v2_open = True
        self._v2_auth_timer = asyncio.create_task(
            self._enforce_auth_timeout()
        )

    def _origin_allowed(self):
        origins = [
            value
            for key, value in self.scope.get("headers", [])
            if key.lower() == b"origin"
        ]

        if len(origins) > 1:
            return False

        # Native clients may omit Origin; JWT is still mandatory.
        if not origins:
            return True

        try:
            origin = origins[0].decode("ascii").lower()
        except UnicodeDecodeError:
            return False

        allowed = set(
            getattr(
                settings,
                "WEBSOCKET_V2_ALLOWED_ORIGINS",
                (
                    "https://www.townlit.com",
                    "https://townlit.com",
                ),
            )
        )

        if settings.DEBUG:
            allowed.update((
                "https://dev.townlit.com",
                "http://localhost:3000",
                "http://127.0.0.1:3000",
            ))

        return origin in {item.lower() for item in allowed}

    async def _enforce_auth_timeout(self):
        try:
            await asyncio.sleep(self.AUTH_TIMEOUT_SECONDS)

            if self._v2_open and not self._v2_authenticated:
                await self._reject(self.CLOSE_AUTH_TIMEOUT)
        except asyncio.CancelledError:
            return

    async def _enforce_session_expiry(self):
        try:
            remaining = max(0.0, self._v2_expires_at - time.time())
            await asyncio.sleep(remaining)

            if self._v2_open and self._v2_authenticated:
                await self._reject(self.CLOSE_UNAUTHORIZED)

        except asyncio.CancelledError:
            return

    async def _monitor_session_access(self):
        """Bound the lifetime of a socket whose account or device was revoked."""
        try:
            while self._v2_open and self._v2_authenticated:
                await asyncio.sleep(self.SESSION_ACCESS_CHECK_SECONDS)

                if not self._v2_open or not self._v2_authenticated:
                    return

                try:
                    allowed = await check_websocket_session_access(
                        self.user.id,
                        self.device_id,
                    )
                except Exception:
                    logger.warning(
                        "[WS V2] Session revalidation unavailable"
                    )
                    allowed = False

                if not allowed:
                    await self._reject(self.CLOSE_DEVICE_REVOKED)
                    return
        except asyncio.CancelledError:
            return

    async def close(self, code=None, reason=None):
        self._v2_close_requested = True
        await super().close(code=code, reason=reason)

    async def _reject(self, code):
        self._v2_open = False
        self._v2_authenticated = False
        self.connected = False
        await self.close(code=code)

    async def receive(self, text_data=None, bytes_data=None):
        if not self._v2_open:
            return

        if self._v2_authenticated:
            if time.time() >= self._v2_expires_at:
                await self._reject(self.CLOSE_UNAUTHORIZED)
                return

            if text_data is None:
                await self._reject(self.CLOSE_INVALID_AUTH)
                return

            if len(text_data.encode("utf-8")) > self.MAX_APPLICATION_MESSAGE_BYTES:
                await self._reject(self.CLOSE_INVALID_AUTH)
                return

            await super().receive(text_data)
            return

        if not isinstance(text_data, str):
            await self._reject(self.CLOSE_INVALID_AUTH)
            return

        if len(text_data.encode("utf-8")) > self.MAX_AUTH_MESSAGE_BYTES:
            await self._reject(self.CLOSE_INVALID_AUTH)
            return

        try:
            message = json.loads(text_data)
        except (ValueError, TypeError):
            await self._reject(self.CLOSE_INVALID_AUTH)
            return

        if (
            not isinstance(message, dict)
            or message.get("type") != "auth"
            or set(message) - {"type", "token", "device_id"}
        ):
            await self._reject(self.CLOSE_INVALID_AUTH)
            return

        device_id = message.get("device_id", "")
        if device_id is None:
            device_id = ""

        if not isinstance(device_id, str):
            await self._reject(self.CLOSE_INVALID_AUTH)
            return

        device_id = device_id.strip().lower()

        if not device_id or not re.fullmatch(
            r"[a-z0-9._-]{1,128}",
            device_id,
        ):
            await self._reject(self.CLOSE_INVALID_AUTH)
            return

        user = await authenticate_websocket_access_token(
            message.get("token")
        )

        if not self._v2_open:
            return

        if user is None:
            await self._reject(self.CLOSE_UNAUTHORIZED)
            return

        try:
            expires_at = int(AccessToken(message["token"])["exp"])
        except (TokenError, KeyError, TypeError, ValueError):
            await self._reject(self.CLOSE_UNAUTHORIZED)
            return

        if expires_at <= time.time():
            await self._reject(self.CLOSE_UNAUTHORIZED)
            return

        # Device and mutable account state must pass *before* any handler runs.
        try:
            device_allowed = await check_websocket_session_access(
                user.id, device_id
            )
        except Exception:
            logger.warning("[WS V2] Initial device authorization unavailable")
            device_allowed = False

        if not device_allowed:
            await self._reject(self.CLOSE_DEVICE_REVOKED)
            return

        if not self._v2_open:
            return

        self.user = user
        self.scope["user"] = user
        self.device_id = device_id
        self._v2_authenticated = True
        self._v2_expires_at = expires_at
        self._v2_expiry_task = asyncio.create_task(
            self._enforce_session_expiry()
        )

        if self._v2_auth_timer:
            self._v2_auth_timer.cancel()

        try:
            await self._activate_authenticated_session(
                accept_socket=False,
                strict_handlers=True,
            )
        except Exception:
            logger.exception("[WS V2] Activation failed")
            if self._v2_close_requested:
                self._v2_open = False
                self._v2_authenticated = False
                self.connected = False
                return
            await self._reject(1011)
            return

        if self._v2_open and self._v2_authenticated:
            self._v2_access_monitor = asyncio.create_task(
                self._monitor_session_access()
            )

    async def safe_send_json(self, data):
        if not getattr(self, "_v2_authenticated", False):
            return

        if time.time() >= self._v2_expires_at:
            await self._reject(self.CLOSE_UNAUTHORIZED)
            return

        await super().safe_send_json(data)

    async def dispatch_event(self, event):
        if not getattr(self, "_v2_authenticated", False):
            return

        if time.time() >= self._v2_expires_at:
            await self._reject(self.CLOSE_UNAUTHORIZED)
            return

        await super().dispatch_event(event)

    async def disconnect(self, close_code):
        self._v2_open = False
        self._v2_authenticated = False

        timer = getattr(self, "_v2_auth_timer", None)
        if timer and timer is not asyncio.current_task():
            timer.cancel()

        expiry_task = getattr(self, "_v2_expiry_task", None)
        if expiry_task and expiry_task is not asyncio.current_task():
            expiry_task.cancel()

        monitor = getattr(self, "_v2_access_monitor", None)
        if monitor and monitor is not asyncio.current_task():
            monitor.cancel()

        await super().disconnect(close_code)
