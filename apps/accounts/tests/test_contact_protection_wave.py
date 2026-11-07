# apps/accounts/tests/test_contact_protection_wave.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#
import base64
import json
import os
from io import StringIO
from unittest.mock import patch
from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from apps.accounts.services.contact_protection import index_matches

class ContactShadowTests(TestCase):
    def setUp(self):
        self.patcher = patch.dict(os.environ, {
            "TOWNLIT_DP_FERNET_KEYS_JSON": json.dumps({"dev_1": Fernet.generate_key().decode()}),
            "TOWNLIT_DP_ACTIVE_KEY_ID": "dev_1",
            "TOWNLIT_DP_BLIND_INDEX_KEYS_JSON": json.dumps({"dev_1": base64.urlsafe_b64encode(os.urandom(32)).decode()}),
            "TOWNLIT_DP_BLIND_INDEX_ACTIVE_KEY_ID": "dev_1",
        })
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_creation_shadows_email_and_mobile(self):
        User = get_user_model()
        u = User.objects.create_user(email="Contact@Example.test", username="contacttest",
                                     mobile_number="+16045550123", password="TestPassword123!")
        u.refresh_from_db()
        self.assertNotIn("Contact@Example.test", u.email_encrypted)
        self.assertNotIn("+16045550123", u.mobile_number_encrypted)
        self.assertTrue(index_matches(u.email_blind_index, u.email, field="email"))
        self.assertTrue(index_matches(u.mobile_number_blind_index, u.mobile_number, field="mobile_number"))

    def test_update_fields_and_backfill(self):
        User = get_user_model()
        u = User.objects.create_user(email="first@example.test", username="contactchange",
                                     password="TestPassword123!")
        u.email = "new@example.test"
        u.mobile_number = "+16045550555"
        u.save(update_fields=["email", "mobile_number"])
        u.refresh_from_db()
        self.assertEqual(u.email, "new@example.test")
        self.assertEqual(u.mobile_number, "+16045550555")
        with self.assertRaises(ValueError):
            User.objects.filter(pk=u.pk).update(email="unsafe@example.test")
        out = StringIO()
        call_command("backfill_contact_protection", "--verify-only", stdout=out)
        self.assertIn("conflicts=0", out.getvalue())

    def test_legacy_backfill(self):
        User = get_user_model()
        u = User.objects.create_user(email="backfill@example.test", username="contactbackfill",
                                     mobile_number="+16045550111", password="TestPassword123!")
        User._base_manager.filter(pk=u.pk).update(email_encrypted=None,
                email_blind_index=None, mobile_number_encrypted=None,
                mobile_number_blind_index=None)
        out = StringIO()
        call_command("backfill_contact_protection", "--apply", stdout=out)
        self.assertIn("conflicts=0", out.getvalue())
        out2 = StringIO()
        call_command("backfill_contact_protection", "--verify-only", stdout=out2)
        self.assertIn("pending=0", out2.getvalue())

    def test_null_phone_legacy_record_is_not_pending(self):
        User = get_user_model()
        user = User.objects.create_user(email="nullphone@example.test", username="nullphone",
                                        password="TestPassword123!")
        User._base_manager.filter(pk=user.pk).update(
            mobile_number=None, mobile_number_encrypted=None, mobile_number_blind_index=None,
        )
        out = StringIO()
        call_command("backfill_contact_protection", "--verify-only", stdout=out)
        self.assertIn("pending=0", out.getvalue())
