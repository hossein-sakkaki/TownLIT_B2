# apps/notifications/tests/test_organization_notification_context.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-03.
# Last Update by Hossein Sakkaki on 2026-10-03.
#

from types import SimpleNamespace

from django.db import models
from django.test import SimpleTestCase

from apps.notifications.models import Notification
from apps.notifications.serializers import NotificationSerializer


class OrganizationNotificationModelContractTests(SimpleTestCase):
    def test_notification_has_nullable_organization_context(self):
        field = Notification._meta.get_field(
            "organization_context"
        )

        self.assertTrue(field.null)
        self.assertTrue(field.blank)

        self.assertEqual(
            field.remote_field.model._meta.label_lower,
            "organizations.organization",
        )

    def test_organization_context_uses_cascade_delete(self):
        field = Notification._meta.get_field(
            "organization_context"
        )

        self.assertIs(
            field.remote_field.on_delete,
            models.CASCADE,
        )

    def test_organization_context_related_name_is_stable(self):
        field = Notification._meta.get_field(
            "organization_context"
        )

        self.assertEqual(
            field.remote_field.related_name,
            "context_notifications",
        )

    def test_notification_has_context_list_index(self):
        indexes = {
            tuple(index.fields)
            for index in Notification._meta.indexes
        }

        self.assertIn(
            (
                "user",
                "organization_context",
                "-created_at",
            ),
            indexes,
        )

    def test_notification_has_context_unread_index(self):
        indexes = {
            tuple(index.fields)
            for index in Notification._meta.indexes
        }

        self.assertIn(
            (
                "user",
                "organization_context",
                "is_read",
            ),
            indexes,
        )


class OrganizationNotificationSerializerContractTests(
    SimpleTestCase
):
    def setUp(self):
        self.serializer = NotificationSerializer()

    def test_null_context_is_personal(self):
        notification = SimpleNamespace(
            organization_context_id=None,
            organization_context=None,
        )

        self.assertEqual(
            self.serializer.get_notification_context(
                notification
            ),
            "personal",
        )

    def test_organization_context_is_organization(self):
        organization = SimpleNamespace(
            public_id="00000000-0000-0000-0000-000000000001",
            slug="townlit-society",
            name="TownLIT Society",
            short_name="TownLIT",
        )

        notification = SimpleNamespace(
            organization_context_id=15,
            organization_context=organization,
        )

        self.assertEqual(
            self.serializer.get_notification_context(
                notification
            ),
            "organization",
        )

    def test_personal_notification_has_no_organization_payload(
        self,
    ):
        notification = SimpleNamespace(
            organization_context_id=None,
            organization_context=None,
        )

        self.assertIsNone(
            self.serializer.get_organization(
                notification
            )
        )

    def test_organization_payload_contains_public_identity(
        self,
    ):
        organization = SimpleNamespace(
            public_id="00000000-0000-0000-0000-000000000001",
            slug="townlit-society",
            name="TownLIT Society",
            short_name="TownLIT",
        )

        notification = SimpleNamespace(
            organization_context_id=15,
            organization_context=organization,
        )

        payload = self.serializer.get_organization(
            notification
        )

        self.assertEqual(
            payload,
            {
                "public_id": (
                    "00000000-0000-0000-0000-000000000001"
                ),
                "slug": "townlit-society",
                "name": "TownLIT Society",
                "short_name": "TownLIT",
            },
        )

    def test_missing_short_name_serializes_as_empty_string(
        self,
    ):
        organization = SimpleNamespace(
            public_id="00000000-0000-0000-0000-000000000001",
            slug="townlit-society",
            name="TownLIT Society",
            short_name=None,
        )

        notification = SimpleNamespace(
            organization_context_id=15,
            organization_context=organization,
        )

        payload = self.serializer.get_organization(
            notification
        )

        self.assertEqual(
            payload["short_name"],
            "",
        )