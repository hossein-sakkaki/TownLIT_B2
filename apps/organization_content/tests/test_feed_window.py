# apps/organization_content/tests/test_feed_window.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-27.
# Last Update by Hossein Sakkaki on 2026-09-27.

from datetime import timedelta
from django.test import SimpleTestCase
from django.utils import timezone

from apps.organization_content.models import OrganizationFeedEntry


class FeedWindowTests(SimpleTestCase):
    def test_active_entry_before_expiration(self):
        now = timezone.now()
        entry = OrganizationFeedEntry(
            is_active=True, starts_at=now - timedelta(minutes=1),
            expires_at=now + timedelta(minutes=1),
        )
        self.assertTrue(entry.is_in_display_window(now=now))

    def test_expired_entry_is_hidden(self):
        now = timezone.now()
        entry = OrganizationFeedEntry(
            is_active=True, starts_at=now - timedelta(days=2),
            expires_at=now - timedelta(seconds=1),
        )
        self.assertFalse(entry.is_in_display_window(now=now))

    def test_unpublished_entry_is_hidden(self):
        now = timezone.now()
        entry = OrganizationFeedEntry(
            is_active=False, starts_at=now - timedelta(days=2),
        )
        self.assertFalse(entry.is_in_display_window(now=now))
