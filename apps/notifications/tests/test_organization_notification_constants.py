# apps/notifications/tests/test_organization_notification_constants.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-03.
# Last Update by Hossein Sakkaki on 2026-10-03.
#

from django.test import SimpleTestCase

from apps.notifications.constants import (
    CHANNEL_PUSH,
    CHANNEL_WS,
    NOTIFICATION_TYPES,
    NOTIFICATION_TYPES_EXCLUDED_FROM_NOTIFICATION_CENTER,
    NOTIFICATION_TYPES_EXCLUDED_FROM_PREFERENCES,
    NOTIFICATION_TYPES_NO_EMAIL,
    ORGANIZATION_NOTIFICATION_TYPES,
    notification_default_channels,
)


class OrganizationNotificationConstantsTests(
    SimpleTestCase
):
    def test_organization_notification_types_exist(self):
        self.assertTrue(
            ORGANIZATION_NOTIFICATION_TYPES
        )

    def test_organization_notification_types_are_unique(self):
        organization_types = list(
            ORGANIZATION_NOTIFICATION_TYPES
        )

        self.assertEqual(
            len(organization_types),
            len(set(organization_types)),
        )

    def test_all_organization_types_use_expected_prefix(self):
        for notification_type in (
            ORGANIZATION_NOTIFICATION_TYPES
        ):
            with self.subTest(
                notification_type=notification_type
            ):
                self.assertTrue(
                    notification_type.startswith(
                        "organization_"
                    )
                )

    def test_organization_types_are_registered(self):
        registered = {
            value
            for value, _label in NOTIFICATION_TYPES
        }

        self.assertTrue(
            ORGANIZATION_NOTIFICATION_TYPES
            <= registered
        )

    def test_organization_types_are_not_user_preferences(
        self,
    ):
        self.assertTrue(
            ORGANIZATION_NOTIFICATION_TYPES
            <= NOTIFICATION_TYPES_EXCLUDED_FROM_PREFERENCES
        )

    def test_organization_types_do_not_send_email(self):
        self.assertTrue(
            ORGANIZATION_NOTIFICATION_TYPES
            <= NOTIFICATION_TYPES_NO_EMAIL
        )

    def test_organization_types_are_visible_in_notification_center(
        self,
    ):
        overlap = (
            ORGANIZATION_NOTIFICATION_TYPES
            & NOTIFICATION_TYPES_EXCLUDED_FROM_NOTIFICATION_CENTER
        )

        self.assertEqual(
            overlap,
            set(),
        )

    def test_organization_default_channels_are_push_and_ws(
        self,
    ):
        expected = CHANNEL_PUSH | CHANNEL_WS

        for notification_type in (
            ORGANIZATION_NOTIFICATION_TYPES
        ):
            with self.subTest(
                notification_type=notification_type
            ):
                self.assertEqual(
                    notification_default_channels(
                        notification_type
                    ),
                    expected,
                )