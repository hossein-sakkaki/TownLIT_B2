# apps/notifications/tests/test_organization_notification_presentation.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-03.
# Last Update by Hossein Sakkaki on 2026-10-03.
#

from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.notifications.services.organization_presentation import (
    organization_audit_copy,
    subscription_event_copy,
)


class OrganizationNotificationPresentationTests(
    SimpleTestCase
):
    def _organization(self):
        return SimpleNamespace(
            name="TownLIT Society",
        )

    def _user(
        self,
        *,
        name="Hossein",
        family="Sakkaki",
        username="hossein",
    ):
        return SimpleNamespace(
            name=name,
            family=family,
            username=username,
        )

    def test_membership_request_copy(self):
        audit_log = SimpleNamespace(
            organization=self._organization(),
            target_user=self._user(),
            actor=None,
            action="membership_requested",
        )

        title, message = organization_audit_copy(
            audit_log
        )

        self.assertEqual(
            title,
            "New membership request",
        )

        self.assertEqual(
            message,
            (
                "Hossein Sakkaki requested to join "
                "TownLIT Society."
            ),
        )

    def test_membership_invitation_copy(self):
        audit_log = SimpleNamespace(
            organization=self._organization(),
            target_user=self._user(),
            actor=None,
            action="membership_invited",
        )

        title, message = organization_audit_copy(
            audit_log
        )

        self.assertEqual(
            title,
            "Organization invitation",
        )

        self.assertEqual(
            message,
            (
                "You were invited to join "
                "TownLIT Society."
            ),
        )

    def test_unknown_audit_action_uses_safe_fallback(self):
        audit_log = SimpleNamespace(
            organization=self._organization(),
            target_user=None,
            actor=None,
            action="future_organization_action",
        )

        title, message = organization_audit_copy(
            audit_log
        )

        self.assertEqual(
            title,
            "Organization update",
        )

        self.assertEqual(
            message,
            (
                "There is an update for "
                "TownLIT Society."
            ),
        )

    def test_trial_started_subscription_copy(self):
        event = SimpleNamespace(
            event_type="trial_started",
        )

        notification_type, title, message = (
            subscription_event_copy(
                event,
                self._organization(),
            )
        )

        self.assertEqual(
            notification_type,
            "organization_subscription_trial_started",
        )

        self.assertEqual(
            title,
            "Organization trial started",
        )

        self.assertEqual(
            message,
            (
                "A subscription trial started for "
                "TownLIT Society."
            ),
        )

    def test_subscription_activated_copy(self):
        event = SimpleNamespace(
            event_type="subscription_activated",
        )

        notification_type, title, message = (
            subscription_event_copy(
                event,
                self._organization(),
            )
        )

        self.assertEqual(
            notification_type,
            "organization_subscription_activated",
        )

        self.assertEqual(
            title,
            "Organization subscription active",
        )

        self.assertEqual(
            message,
            (
                "The subscription for "
                "TownLIT Society is active."
            ),
        )

    def test_unknown_subscription_event_is_ignored(self):
        event = SimpleNamespace(
            event_type="some_future_event",
        )

        self.assertEqual(
            subscription_event_copy(
                event,
                self._organization(),
            ),
            ("", "", ""),
        )