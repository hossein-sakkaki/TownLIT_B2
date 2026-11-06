# apps/accounts/tests/test_session_security_foundation.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-05.
# Last Update by Hossein Sakkaki on 2026-11-05.
#

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models.session_security import UserAuthSessionState
from apps.accounts.services.session_security import (
    get_session_generation,
    increment_session_generation,
)


class SessionSecurityFoundationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="session-generation@example.com",
            password="ExistingPassword42!",
        )

    def test_existing_user_has_generation_zero_without_backfill(self):
        self.assertEqual(get_session_generation(self.user.pk), 0)
        self.assertFalse(
            UserAuthSessionState.objects.filter(user_id=self.user.pk).exists()
        )

    def test_first_revocation_creates_one_state_row(self):
        self.assertEqual(increment_session_generation(self.user.pk), 1)
        self.assertEqual(get_session_generation(self.user.pk), 1)
        state = UserAuthSessionState.objects.get(user_id=self.user.pk)
        self.assertIsNotNone(state.last_revoked_at)
        self.assertEqual(UserAuthSessionState.objects.count(), 1)

    def test_repeated_revocations_increment_without_new_rows(self):
        self.assertEqual(increment_session_generation(self.user.pk), 1)
        self.assertEqual(increment_session_generation(self.user.pk), 2)
        self.assertEqual(increment_session_generation(self.user.pk), 3)
        self.assertEqual(get_session_generation(self.user.pk), 3)
        self.assertEqual(UserAuthSessionState.objects.count(), 1)

    def test_revocation_is_per_account_and_does_not_change_password(self):
        other = get_user_model().objects.create_user(
            email="other-session-generation@example.com",
            password="OtherPassword42!",
        )
        old_password_hash = self.user.password
        self.assertEqual(increment_session_generation(self.user.pk), 1)
        self.assertEqual(get_session_generation(other.pk), 0)
        self.user.refresh_from_db()
        self.assertEqual(self.user.password, old_password_hash)
        self.assertTrue(self.user.check_password("ExistingPassword42!"))
