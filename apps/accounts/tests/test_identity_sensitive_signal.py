# apps/accounts/tests/test_identity_sensitive_signal.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Regression checks for identity revocation with encrypted birthday storage."""

import json
import os
from datetime import date
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.accounts.constants.identity_verification import (
    IV_STATUS_REVOKED,
    IV_STATUS_VERIFIED,
)
from apps.accounts.models.identity import IdentityVerification


class EncryptedBirthdayIdentitySignalTests(TestCase):
    def setUp(self):
        self.key_patch = patch.dict(
            os.environ,
            {
                "TOWNLIT_DP_FERNET_KEYS_JSON": json.dumps(
                    {"dev_1": Fernet.generate_key().decode("ascii")}
                ),
                "TOWNLIT_DP_ACTIVE_KEY_ID": "dev_1",
            },
        )
        self.key_patch.start()
        self.addCleanup(self.key_patch.stop)

        self.user = get_user_model().objects.create_user(
            email="identity-signal@example.test",
            username="idsignaltest",
            name="Before",
            birthday=date(1990, 3, 4),
            password="TestOnlyPassword123!",
        )
        self.identity = IdentityVerification.objects.create(
            user=self.user,
            method="admin",
            status=IV_STATUS_VERIFIED,
            level="basic",
            verified_at=timezone.now(),
        )

    def test_birthday_change_revokes_verified_identity(self):
        self.user.birthday = date(1991, 5, 6)
        self.user.save(update_fields=["birthday"])
        self.identity.refresh_from_db()
        self.assertEqual(self.identity.status, IV_STATUS_REVOKED)
        self.assertIsNotNone(self.identity.revoked_at)
        self.assertIn("birthday", self.identity.notes)
        self.user.refresh_from_db()
        self.assertEqual(self.user.birthday, date(1991, 5, 6))

    def test_name_change_still_revokes_verified_identity(self):
        self.user.name = "After"
        self.user.save(update_fields=["name"])
        self.identity.refresh_from_db()
        self.assertEqual(self.identity.status, IV_STATUS_REVOKED)
        self.assertIn("name", self.identity.notes)

    def test_unrelated_partial_save_does_not_revoke_identity(self):
        # An in-memory birthday change excluded from update_fields is not persisted.
        self.user.birthday = date(1992, 7, 8)
        self.user.is_active = True
        self.user.save(update_fields=["is_active"])
        self.identity.refresh_from_db()
        self.assertEqual(self.identity.status, IV_STATUS_VERIFIED)
        database_user = get_user_model().objects.get(pk=self.user.pk)
        self.assertEqual(database_user.birthday, date(1990, 3, 4))

    def test_same_birthday_does_not_revoke_identity(self):
        self.user.birthday = date(1990, 3, 4)
        self.user.save(update_fields=["birthday"])
        self.identity.refresh_from_db()
        self.assertEqual(self.identity.status, IV_STATUS_VERIFIED)
