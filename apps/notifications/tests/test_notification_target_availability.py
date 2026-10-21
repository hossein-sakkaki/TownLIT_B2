# apps/notifications/tests/test_notification_target_availability.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-21.
# Last Update by Hossein Sakkaki on 2026-10-21.
#

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.notifications.models import Notification


class NotificationTargetAvailabilityTests(SimpleTestCase):
    databases = set()

    def make_notification(self, **overrides):
        values = {
            "user_id": 1,
            "message": "Notification target availability test.",
            "notification_type": "townlit_announcement",
        }
        values.update(overrides)
        return Notification(**values)

    def test_target_availability_contract_without_database(self):
        # System / Campaign notification with no target is valid.
        notification = self.make_notification()

        with patch.object(Notification, "get_target_safe") as get_target_safe:
            self.assertFalse(notification.is_target_unavailable())
            get_target_safe.assert_not_called()

        # Partial GenericForeignKey references are invalid.
        notification = self.make_notification(
            target_content_type_id=10,
            target_object_id=None,
        )
        self.assertTrue(notification.is_target_unavailable())

        notification = self.make_notification(
            target_content_type_id=None,
            target_object_id=20,
        )
        self.assertTrue(notification.is_target_unavailable())

        # A referenced target that no longer exists is stale.
        notification = self.make_notification(
            target_content_type_id=10,
            target_object_id=20,
        )

        with patch.object(Notification, "get_target_safe", return_value=None):
            self.assertTrue(notification.is_target_unavailable())

        # A healthy referenced target remains valid.
        healthy_target = SimpleNamespace(
            is_active=True,
            is_hidden=False,
            is_suspended=False,
            is_restricted=False,
        )

        with patch.object(Notification, "get_target_safe", return_value=healthy_target):
            self.assertFalse(notification.is_target_unavailable())

        # Existing visibility protections must remain intact.
        restricted_states = (
            {"is_active": False},
            {"is_hidden": True},
            {"is_suspended": True},
            {"is_restricted": True},
        )

        for state in restricted_states:
            target = SimpleNamespace(
                is_active=state.get("is_active", True),
                is_hidden=state.get("is_hidden", False),
                is_suspended=state.get("is_suspended", False),
                is_restricted=state.get("is_restricted", False),
            )

            with self.subTest(state=state):
                with patch.object(Notification, "get_target_safe", return_value=target):
                    self.assertTrue(notification.is_target_unavailable())