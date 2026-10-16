# apps/notifications/tests/test_organization_notification_signals.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-03.
# Last Update by Hossein Sakkaki on 2026-10-03.
#

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.notifications.signals.organization_signals import (
    organization_audit_notification_signal,
    organization_subscription_notification_signal,
)


class OrganizationNotificationSignalTests(
    SimpleTestCase
):
    @patch(
        "apps.notifications.signals."
        "organization_signals.transaction.on_commit"
    )
    def test_new_audit_log_publishes_after_commit(
        self,
        on_commit_mock,
    ):
        instance = SimpleNamespace(
            pk=101,
        )

        organization_audit_notification_signal(
            sender=object(),
            instance=instance,
            created=True,
        )

        on_commit_mock.assert_called_once()

        callback = on_commit_mock.call_args.args[0]

        with patch(
            "apps.notifications.signals."
            "organization_signals._safe_publish"
        ) as safe_publish_mock:
            callback()

        safe_publish_mock.assert_called_once()

        callback_function = (
            safe_publish_mock.call_args.args[0]
        )
        callback_kwargs = (
            safe_publish_mock.call_args.kwargs
        )

        self.assertEqual(
            callback_function.__name__,
            "publish_organization_audit_notification",
        )

        self.assertEqual(
            callback_kwargs,
            {
                "audit_log_id": 101,
            },
        )

    @patch(
        "apps.notifications.signals."
        "organization_signals.transaction.on_commit"
    )
    def test_existing_audit_log_does_not_publish_again(
        self,
        on_commit_mock,
    ):
        instance = SimpleNamespace(
            pk=101,
        )

        organization_audit_notification_signal(
            sender=object(),
            instance=instance,
            created=False,
        )

        on_commit_mock.assert_not_called()

    @patch(
        "apps.notifications.signals."
        "organization_signals.transaction.on_commit"
    )
    def test_new_subscription_event_publishes_after_commit(
        self,
        on_commit_mock,
    ):
        instance = SimpleNamespace(
            pk=202,
        )

        organization_subscription_notification_signal(
            sender=object(),
            instance=instance,
            created=True,
        )

        on_commit_mock.assert_called_once()

        callback = on_commit_mock.call_args.args[0]

        with patch(
            "apps.notifications.signals."
            "organization_signals._safe_publish"
        ) as safe_publish_mock:
            callback()

        safe_publish_mock.assert_called_once()

        callback_function = (
            safe_publish_mock.call_args.args[0]
        )
        callback_kwargs = (
            safe_publish_mock.call_args.kwargs
        )

        self.assertEqual(
            callback_function.__name__,
            "publish_subscription_event_notification",
        )

        self.assertEqual(
            callback_kwargs,
            {
                "event_id": 202,
            },
        )

    @patch(
        "apps.notifications.signals."
        "organization_signals.transaction.on_commit"
    )
    def test_existing_subscription_event_does_not_publish_again(
        self,
        on_commit_mock,
    ):
        instance = SimpleNamespace(
            pk=202,
        )

        organization_subscription_notification_signal(
            sender=object(),
            instance=instance,
            created=False,
        )

        on_commit_mock.assert_not_called()