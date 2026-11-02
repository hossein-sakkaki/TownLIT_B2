# tests/test_ws_v2_gateway.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-23.
# Last Update by Hossein Sakkaki on 2026-10-23.

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from rest_framework_simplejwt.tokens import AccessToken
import time

from asgiref.testing import ApplicationCommunicator
from urllib.parse import urlsplit
import asyncio
import json


class WebsocketCommunicator:
    """
    Minimal ASGI WebSocket test client.

    Uses asgiref directly, without requiring Daphne.
    """

    def __init__(self, application, path, headers=None):
        parsed = urlsplit(path)

        scope = {
            "type": "websocket",
            "asgi": {
                "version": "3.0",
                "spec_version": "2.4",
            },
            "path": parsed.path,
            "raw_path": parsed.path.encode("utf-8"),
            "query_string": parsed.query.encode("utf-8"),
            "headers": headers or [],
            "subprotocols": [],
            "scheme": "ws",
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
        }

        self._driver = ApplicationCommunicator(
            application,
            scope,
        )
        self._accepted = False
        self._started = False

    async def connect(self):
        self._started = True

        await self._driver.send_input({
            "type": "websocket.connect",
        })

        event = await self.receive_output(timeout=1)

        if event["type"] == "websocket.accept":
            self._accepted = True
            return True, event.get("subprotocol")

        if event["type"] == "websocket.close":
            return False, event.get("code")

        raise AssertionError(
            f"Unexpected handshake event: {event['type']}"
        )

    async def send_json_to(self, data):
        await self._driver.send_input({
            "type": "websocket.receive",
            "text": json.dumps(data),
        })

    async def receive_json_from(self, timeout=1):
        event = await self.receive_output(timeout=timeout)

        if event["type"] != "websocket.send":
            raise AssertionError(
                f"Expected websocket.send, got {event['type']}"
            )

        return json.loads(event["text"])

    async def receive_output(self, timeout=1):
        return await self._driver.receive_output(
            timeout=timeout,
        )

    async def receive_nothing(self, timeout=0.1):
        return await self._driver.receive_nothing(
            timeout=timeout,
        )

    async def disconnect(self):
        if not self._started:
            return

        if not self._accepted:
            self._driver.stop(exceptions=False)
            return

        await self._driver.send_input({
            "type": "websocket.disconnect",
            "code": 1000,
        })

        try:
            await self._driver.wait(timeout=1)
        except asyncio.TimeoutError:
            self._driver.stop(exceptions=False)


from django.test import override_settings

from townlit_b.asgi import application
from apps.main.middleware import JWTAuthMiddleware
from apps.core.websocket.consumer import CentralWebSocketConsumer
from apps.core.websocket.consumer_v2 import CentralWebSocketConsumerV2


class WebSocketV2GatewayTests(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.settings_override = override_settings(
            CHANNEL_LAYERS={
                "default": {
                    "BACKEND": "channels.layers.InMemoryChannelLayer",
                }
            }
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

        self.user = SimpleNamespace(
            id=123,
            is_authenticated=True,
            is_anonymous=False,
        )

    def socket(self, path, headers=None):
        kwargs = {}
        if headers is not None:
            kwargs["headers"] = headers

        client = WebsocketCommunicator(application, path, **kwargs)
        self.addAsyncCleanup(client.disconnect)
        return client

    async def expect_close(self, client, code):
        event = await client.receive_output(timeout=1)
        self.assertEqual(event["type"], "websocket.close")
        self.assertEqual(event.get("code"), code)

    async def expect_connected_message(self, client):
        for _ in range(3):
            message = await client.receive_json_from(timeout=1)
            if message.get("type") == "connected":
                return message

        self.fail("Authenticated connected message not received")

    async def test_v2_no_handlers_before_auth(self):
        with patch.object(
            CentralWebSocketConsumer,
            "_register_handlers",
        ) as register:
            client = self.socket("/ws/v2/")
            connected, _ = await client.connect()

            self.assertTrue(connected)
            self.assertTrue(
                await client.receive_nothing(timeout=0.05)
            )
            register.assert_not_called()

    async def test_v2_rejects_untrusted_origin(self):
        client = self.socket(
            "/ws/v2/",
            headers=[(b"origin", b"https://untrusted.example")],
        )
        connected, code = await client.connect()

        self.assertFalse(connected)
        self.assertEqual(code, 4403)

    async def test_v2_rejects_token_in_url(self):
        client = self.socket("/ws/v2/?token=fake-token")
        connected, code = await client.connect()

        self.assertFalse(connected)
        self.assertEqual(code, 4400)

    async def test_v2_rejects_application_message_before_auth(self):
        client = self.socket("/ws/v2/")
        connected, _ = await client.connect()
        self.assertTrue(connected)

        await client.send_json_to({
            "app": "conversation",
            "type": "typing",
            "data": {},
        })
        await self.expect_close(client, 4400)

    async def test_v2_rejects_invalid_credentials(self):
        with patch(
            "apps.core.websocket.consumer_v2."
            "authenticate_websocket_access_token",
            new_callable=AsyncMock,
            return_value=None,
        ) as authenticate:
            client = self.socket("/ws/v2/")
            connected, _ = await client.connect()
            self.assertTrue(connected)

            await client.send_json_to({
                "type": "auth",
                "token": "fake-invalid-token",
                "device_id": "valid-device",
            })
            await self.expect_close(client, 4401)
            authenticate.assert_awaited_once()

    async def test_v2_rejects_oversized_auth_message(self):
        with patch(
            "apps.core.websocket.consumer_v2."
            "authenticate_websocket_access_token",
            new_callable=AsyncMock,
        ) as authenticate:
            client = self.socket("/ws/v2/")
            connected, _ = await client.connect()
            self.assertTrue(connected)

            await client.send_json_to({
                "type": "auth",
                "token": "x" * 17000,
            })
            await self.expect_close(client, 4400)
            authenticate.assert_not_awaited()

    async def test_v2_auth_timeout(self):
        with patch.object(
            CentralWebSocketConsumerV2,
            "AUTH_TIMEOUT_SECONDS",
            0.05,
        ):
            client = self.socket("/ws/v2/")
            connected, _ = await client.connect()
            self.assertTrue(connected)

            await self.expect_close(client, 4408)

    async def test_v2_valid_auth_activates_gateway(self):
        token = AccessToken()
        token["user_id"] = self.user.id
        signed_token = str(token)

        with patch.object(
            CentralWebSocketConsumer,
            "_register_handlers",
        ) as register:
            with patch(
                "apps.core.websocket.consumer_v2."
                "authenticate_websocket_access_token",
                new_callable=AsyncMock,
                return_value=self.user,
            ) as authenticate:
                client = self.socket("/ws/v2/")
                connected, _ = await client.connect()
                self.assertTrue(connected)

                register.assert_not_called()

                with patch(
                    "apps.core.websocket.consumer_v2."
                    "check_websocket_session_access",
                    new_callable=AsyncMock,
                    return_value=True,
                ):
                    await client.send_json_to({
                        "type": "auth",
                        "token": signed_token,
                        "device_id": "ios-123",
                    })
                    message = await self.expect_connected_message(client)

                self.assertEqual(message["user_id"], 123)
                register.assert_called_once()
                authenticate.assert_awaited_once_with(signed_token)

    async def test_v2_rejects_unregistered_device_before_handlers(self):
        token = AccessToken()
        token["user_id"] = self.user.id
        signed_token = str(token)

        with patch.object(CentralWebSocketConsumer, "_register_handlers") as register:
            with patch(
                "apps.core.websocket.consumer_v2."
                "authenticate_websocket_access_token",
                new_callable=AsyncMock,
                return_value=self.user,
            ):
                with patch(
                    "apps.core.websocket.consumer_v2."
                    "check_websocket_session_access",
                    new_callable=AsyncMock,
                    return_value=False,
                ):
                    client = self.socket("/ws/v2/")
                    connected, _ = await client.connect()
                    self.assertTrue(connected)
                    await client.send_json_to({
                        "type": "auth",
                        "token": signed_token,
                        "device_id": "revoked-device",
                    })
                    await self.expect_close(client, 4406)
                    register.assert_not_called()

    async def test_v2_rejects_missing_device_id_before_handlers(self):
        with patch.object(CentralWebSocketConsumer, "_register_handlers") as register:
            with patch(
                "apps.core.websocket.consumer_v2."
                "authenticate_websocket_access_token",
                new_callable=AsyncMock,
            ) as authenticate:
                client = self.socket("/ws/v2/")
                connected, _ = await client.connect()
                self.assertTrue(connected)
                await client.send_json_to({"type": "auth", "token": "missing-device"})
                await self.expect_close(client, 4400)
                authenticate.assert_not_awaited()
                register.assert_not_called()

    async def test_v2_closes_when_account_or_device_revoked(self):
        token = AccessToken()
        token["user_id"] = self.user.id

        with patch.object(CentralWebSocketConsumer, "_register_handlers"):
            with patch(
                "apps.core.websocket.consumer_v2."
                "authenticate_websocket_access_token",
                new_callable=AsyncMock,
                return_value=self.user,
            ):
                with patch(
                    "apps.core.websocket.consumer_v2."
                    "check_websocket_session_access",
                    new_callable=AsyncMock,
                    side_effect=[True, False],
                ):
                    with patch.object(
                        CentralWebSocketConsumerV2,
                        "SESSION_ACCESS_CHECK_SECONDS",
                        0.05,
                    ):
                        client = self.socket("/ws/v2/")
                        connected, _ = await client.connect()
                        self.assertTrue(connected)
                        await client.send_json_to({
                            "type": "auth",
                            "token": str(token),
                            "device_id": "valid-device",
                        })
                        await self.expect_connected_message(client)
                        for _ in range(5):
                            event = await client.receive_output(timeout=2)
                            if event["type"] == "websocket.close":
                                self.assertEqual(event.get("code"), 4406)
                                break
                        else:
                            self.fail("Revoked session remained connected")


    async def test_v2_handler_denial_stops_remaining_handlers(self):
        token = AccessToken()
        token["user_id"] = self.user.id
        later_connect = AsyncMock()

        def register_handlers(consumer):
            async def deny_connection():
                await consumer.close(code=4406)

            consumer.handlers = {
                "deny": SimpleNamespace(on_connect=deny_connection),
                "later": SimpleNamespace(on_connect=later_connect),
            }

        with patch.object(
            CentralWebSocketConsumer,
            "_register_handlers",
            new=register_handlers,
        ):
            with patch(
                "apps.core.websocket.consumer_v2."
                "authenticate_websocket_access_token",
                new_callable=AsyncMock,
                return_value=self.user,
            ):
                with patch(
                    "apps.core.websocket.consumer_v2."
                    "check_websocket_session_access",
                    new_callable=AsyncMock,
                    return_value=True,
                ):
                    client = self.socket("/ws/v2/")
                    connected, _ = await client.connect()
                    self.assertTrue(connected)
                    await client.send_json_to({
                        "type": "auth",
                        "token": str(token),
                        "device_id": "valid-device",
                    })
                    await self.expect_close(client, 4406)
                    later_connect.assert_not_awaited()

    async def test_v2_closes_when_access_token_expires(self):
        token = AccessToken()
        token["user_id"] = self.user.id
        token["exp"] = int(time.time()) + 2

        with patch.object(
            CentralWebSocketConsumer,
            "_register_handlers",
        ):
            with patch(
                "apps.core.websocket.consumer_v2."
                "authenticate_websocket_access_token",
                new_callable=AsyncMock,
                return_value=self.user,
            ):
                client = self.socket("/ws/v2/")
                connected, _ = await client.connect()
                self.assertTrue(connected)

                with patch(
                    "apps.core.websocket.consumer_v2."
                    "check_websocket_session_access",
                    new_callable=AsyncMock,
                    return_value=True,
                ):
                    await client.send_json_to({
                        "type": "auth",
                        "token": str(token),
                        "device_id": "valid-device",
                    })
                    await self.expect_connected_message(client)

                for _ in range(5):
                    event = await client.receive_output(timeout=4)
                    if event["type"] == "websocket.close":
                        self.assertEqual(event["code"], 4401)
                        break
                else:
                    self.fail("Expired WebSocket was not closed")

    async def test_v1_still_rejects_missing_token(self):
        client = self.socket("/ws/")
        connected, _ = await client.connect()
        self.assertFalse(connected)

    async def test_v1_route_still_accepts_authenticated_user(self):
        with patch.object(
            JWTAuthMiddleware,
            "get_user_from_token",
            new_callable=AsyncMock,
            return_value=self.user,
        ):
            with patch.object(
                CentralWebSocketConsumer,
                "_is_restricted_owner",
                new_callable=AsyncMock,
                return_value=False,
            ):
                with patch.object(
                    CentralWebSocketConsumer,
                    "_register_handlers",
                ):
                    client = self.socket("/ws/?token=fake-v1-token")
                    connected, _ = await client.connect()
                    self.assertTrue(connected)

                    message = await self.expect_connected_message(
                        client
                    )
                    self.assertEqual(message["user_id"], 123)


if __name__ == "__main__":
    unittest.main()
