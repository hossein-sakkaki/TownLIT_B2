# apps/accounts/tests/test_user_privacy_wave.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

import base64
import json
import os
from datetime import date
from io import StringIO
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from apps.accounts.models.identity import IdentityGrant, IdentityAuditLog
from apps.core.crypto.blind_index import BlindIndexer
from apps.core.crypto.field_protection import FieldProtectionIntegrityError


class BlindIndexPrimitiveTests(SimpleTestCase):
    def test_independent_keys_and_purpose_separation(self):
        key = base64.urlsafe_b64encode(os.urandom(32)).decode()
        other = base64.urlsafe_b64encode(os.urandom(32)).decode()
        a = BlindIndexer(keys={"i1": key}, active_key_id="i1")
        b = BlindIndexer(keys={"i1": other}, active_key_id="i1")
        self.assertEqual(a.digest("alice@example.test", purpose="accounts.email"),
                         a.digest("alice@example.test", purpose="accounts.email"))
        self.assertNotEqual(a.digest("alice@example.test", purpose="accounts.email"),
                            a.digest("alice@example.test", purpose="accounts.mobile"))
        self.assertNotEqual(a.digest("alice@example.test", purpose="accounts.email"),
                            b.digest("alice@example.test", purpose="accounts.email"))


class Phase4ShadowWriteTests(TestCase):
    def setUp(self):
        self.patcher = patch.dict(os.environ, {
            "TOWNLIT_DP_FERNET_KEYS_JSON": json.dumps({"dev_1": Fernet.generate_key().decode()}),
            "TOWNLIT_DP_ACTIVE_KEY_ID": "dev_1",
        })
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        User = get_user_model()
        self.user = User.objects.create_user(email="phase4@example.test",
                                             username="phase4test", birthday=date(1999, 7, 8),
                                             password="TestingOnlyPassword123!")

    def test_shadow_user_and_identity_fields(self):
        self.assertEqual(self.user.birthday, date(1999, 7, 8))
        self.assertTrue(self.user.birthday_encrypted.startswith("tdp1:"))
        grant = IdentityGrant.objects.create(user=self.user, level="basic", source="system",
                                             reason="Sensitive grant reason")
        self.assertTrue(grant.reason_encrypted.startswith("tdp1:"))
        audit = IdentityAuditLog.objects.create(
            user=self.user, action="verified", source="system",
            reason="Private reason", metadata={"private": "مرحبا"}
        )
        self.assertEqual(audit.metadata, {"private": "مرحبا"})
        self.assertTrue(audit.reason_encrypted.startswith("tdp1:"))
        self.assertTrue(audit.metadata_encrypted.startswith("tdp1:"))
        out = StringIO()
        call_command("backfill_user_privacy_wave", "--verify-only", stdout=out)
        self.assertIn("conflicts=0", out.getvalue())
        self.assertIn("pending=0", out.getvalue())
        self.assertNotIn("Private reason", out.getvalue())

    def test_backfill_recovery_from_unfilled_column(self):
        User = get_user_model()
        User._base_manager.filter(pk=self.user.pk).update(birthday_encrypted=None)
        out = StringIO()
        call_command("backfill_user_privacy_wave", "--apply", stdout=out)
        self.assertIn("applied=1", out.getvalue())
        call_command("backfill_user_privacy_wave", "--verify-only", stdout=StringIO())
