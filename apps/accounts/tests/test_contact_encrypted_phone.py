# apps/accounts/tests/test_contact_encrypted_phone.py
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
from apps.accounts.serializers.user_serializers import CustomUserSerializer, PublicCustomUserSerializer
from apps.accounts.services.contact_protection import index_matches

class EncryptedContactTests(TestCase):
    def setUp(self):
        self.patcher = patch.dict(os.environ, {
            "TOWNLIT_DP_FERNET_KEYS_JSON": json.dumps({"dev_1": Fernet.generate_key().decode()}),
            "TOWNLIT_DP_ACTIVE_KEY_ID": "dev_1",
            "TOWNLIT_DP_BLIND_INDEX_KEYS_JSON": json.dumps({"dev_1": base64.urlsafe_b64encode(os.urandom(32)).decode()}),
            "TOWNLIT_DP_BLIND_INDEX_ACTIVE_KEY_ID": "dev_1",
        })
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_phone_is_not_a_database_field(self):
        User = get_user_model()
        names = {f.name for f in User._meta.concrete_fields}
        self.assertNotIn("mobile_number", names)
        self.assertIn("mobile_number_encrypted", names)
        u = User.objects.create_user(email="contactb@example.test", username="contactb",
                                     mobile_number="+16045550122", password="TestPassword123!")
        u.refresh_from_db()
        self.assertEqual(u.mobile_number, "+16045550122")
        self.assertTrue(index_matches(u.mobile_number_blind_index, u.mobile_number, field="mobile_number"))
        self.assertIn("mobile_number", CustomUserSerializer().fields)
        self.assertIn("mobile_number", PublicCustomUserSerializer().fields)
        self.assertNotIn("mobile_number_encrypted", CustomUserSerializer().fields)

    def test_mobile_update_and_account_deletion_clear_contract(self):
        User = get_user_model()
        u = User.objects.create_user(email="contactupdate@example.test", username="contactupdate",
                                     mobile_number="+16045550124", password="TestPassword123!")
        u.mobile_number = None
        u.save(update_fields=["mobile_number"])
        u.refresh_from_db()
        self.assertIsNone(u.mobile_number)
        self.assertIsNone(u.mobile_number_encrypted)
        self.assertIsNone(u.mobile_number_blind_index)

    def test_emails_remain_legacy_auth_field_with_shadow(self):
        User = get_user_model()
        u = User.objects.create_user(email="contacte@example.test", username="contacte",
                                     password="TestPassword123!")
        self.assertEqual(u.email, "contacte@example.test")
        self.assertEqual(User.USERNAME_FIELD, "email")
        self.assertTrue(u.email_encrypted.startswith("tdp1:"))
        self.assertTrue(index_matches(u.email_blind_index, u.email, field="email"))
        out = StringIO()
        call_command("verify_contact_protection", stdout=out)
        self.assertIn("errors=0", out.getvalue())

    def test_phone_bound_to_user_row(self):
        from apps.core.crypto.field_protection import FieldProtectionIntegrityError
        User = get_user_model()
        first = User.objects.create_user(email="bind1@example.test", username="bind1",
                                         mobile_number="+16045559911", password="TestPassword123!")
        second = User.objects.create_user(email="bind2@example.test", username="bind2",
                                          mobile_number="+16045559922", password="TestPassword123!")
        User._base_manager.filter(pk=second.pk).update(mobile_number_encrypted=first.mobile_number_encrypted)
        second.refresh_from_db()
        with self.assertRaises(FieldProtectionIntegrityError):
            _ = second.mobile_number
