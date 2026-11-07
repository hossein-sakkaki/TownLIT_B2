# apps/accounts/tests/test_contact_protection_wave.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#
import base64
import json
import os
from unittest.mock import patch
from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from apps.accounts.services.contact_protection import index_matches

class ContactCutoverRegressions(TestCase):
    def setUp(self):
        self.patcher = patch.dict(os.environ, {
            "TOWNLIT_DP_FERNET_KEYS_JSON": json.dumps({"dev_1": Fernet.generate_key().decode()}),
            "TOWNLIT_DP_ACTIVE_KEY_ID": "dev_1",
            "TOWNLIT_DP_BLIND_INDEX_KEYS_JSON": json.dumps({"dev_1": base64.urlsafe_b64encode(os.urandom(32)).decode()}),
            "TOWNLIT_DP_BLIND_INDEX_ACTIVE_KEY_ID": "dev_1",
        })
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_email_shadow_and_phone_ciphertext_updated(self):
        User = get_user_model()
        user = User.objects.create_user(email="stageb-first@example.test", username="stagebfirst",
                                        mobile_number="+16045550001", password="TestPassword123!")
        user.email = "stageb-second@example.test"
        user.mobile_number = "+16045550002"
        user.save(update_fields=["email", "mobile_number"])
        user.refresh_from_db()
        self.assertEqual(user.email, "stageb-second@example.test")
        self.assertEqual(user.mobile_number, "+16045550002")
        self.assertTrue(index_matches(user.email_blind_index, user.email, field="email"))
        self.assertTrue(index_matches(user.mobile_number_blind_index, user.mobile_number, field="mobile_number"))
        self.assertTrue(user.email_encrypted.startswith("tdp1:"))

    def test_mass_contact_write_rejected(self):
        User = get_user_model()
        user = User.objects.create_user(email="write-rejected@example.test", username="writereject",
                                        password="TestPassword123!")
        with self.assertRaises(ValueError):
            User.objects.filter(pk=user.pk).update(email="bad@example.test")
        with self.assertRaises(ValueError):
            User.objects.filter(pk=user.pk).update(mobile_number_encrypted="bad")

    def test_backfill_command_disabled_after_cutover(self):
        with self.assertRaises(CommandError):
            call_command("backfill_contact_protection")
