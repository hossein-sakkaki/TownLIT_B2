import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from apps.core.websocket.services import presence_lifecycle


class PresenceUTCCompatibilityTests(unittest.IsolatedAsyncioTestCase):

    async def test_last_seen_uses_aware_utc_datetime(self):
        timestamp = 1760000000
        user_id = 17

        with (
            patch.object(
                presence_lifecycle,
                "set_user_offline",
                new_callable=AsyncMock,
            ),
            patch.object(
                presence_lifecycle,
                "get_online_status_for_users",
                new_callable=AsyncMock,
                return_value={user_id: False},
            ),
            patch.object(
                presence_lifecycle,
                "get_last_seen",
                new_callable=AsyncMock,
                return_value=timestamp,
            ),
        ):
            result = await presence_lifecycle.mark_user_offline(
                user_id,
                "test-socket",
            )

        expected = datetime.fromtimestamp(
            timestamp,
            tz=timezone.utc,
        )

        self.assertEqual(result["user_id"], user_id)
        self.assertFalse(result["is_online"])
        self.assertEqual(result["last_seen_epoch"], timestamp)
        self.assertEqual(result["last_seen"], expected.isoformat())

    async def test_other_active_socket_prevents_offline_update(self):
        user_id = 17

        with (
            patch.object(
                presence_lifecycle,
                "set_user_offline",
                new_callable=AsyncMock,
            ),
            patch.object(
                presence_lifecycle,
                "get_online_status_for_users",
                new_callable=AsyncMock,
                return_value={user_id: True},
            ),
            patch.object(
                presence_lifecycle,
                "get_last_seen",
                new_callable=AsyncMock,
            ) as last_seen,
        ):
            result = await presence_lifecycle.mark_user_offline(
                user_id,
                "test-socket",
            )

        self.assertIsNone(result)
        last_seen.assert_not_awaited()
