# apps/accounts/tests/test_identity_privacy_wave.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

import json
import os
from datetime import timedelta
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.accounts.services.email_change_security import (
    new_email_change_state,
    verify_email_change_codes,
    email_change_expired,
    pending_new_email,
)
from apps.accounts.services.identity_private_fields import (
    encrypt_identity_field,
    decrypt_identity_field,
)
from apps.core.crypto.field_protection import FieldProtectionIntegrityError


class FieldProtectionContractTests(SimpleTestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "TOWNLIT_DP_FERNET_KEYS_JSON": json.dumps({"dev_1": Fernet.generate_key().decode()}),
            "TOWNLIT_DP_ACTIVE_KEY_ID": "dev_1",
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_identity_payload_is_row_bound(self):
        payload = {"session": {"metadata": {"language": "فارسی"}}}
        token = encrypt_identity_field("provider_payload", payload, user_id=101)
        self.assertNotIn("فارسی", token)
        self.assertEqual(decrypt_identity_field("provider_payload", token, 101), payload)
        with self.assertRaises(FieldProtectionIntegrityError):
            decrypt_identity_field("provider_payload", token, 102)

    def test_identity_notes_separate_from_payload(self):
        token = encrypt_identity_field("notes", "پشتیبانی محرمانه", user_id=101)
        self.assertEqual(decrypt_identity_field("notes", token, 101), "پشتیبانی محرمانه")
        with self.assertRaises(FieldProtectionIntegrityError):
            decrypt_identity_field("provider_payload", token, 101)

    def test_email_change_codes_are_hashed_and_email_is_encrypted(self):
        state = new_email_change_state(
            user_id=107,
            old_code="12345",
            new_code="67890",
            new_email="new@example.test",
            expires_at=timezone.now() + timedelta(minutes=8),
        )
        stored = json.dumps(state)
        self.assertNotIn("12345", stored)
        self.assertNotIn("67890", stored)
        self.assertNotIn("new@example.test", stored)
        self.assertTrue(verify_email_change_codes(state, "12345", "67890", user_id=107))
        self.assertFalse(verify_email_change_codes(state, "12345", "11111", user_id=107))
        self.assertEqual(pending_new_email(state, 107), "new@example.test")
        with self.assertRaises(FieldProtectionIntegrityError):
            pending_new_email(state, 108)

    def test_email_change_expiry_and_legacy_compatibility(self):
        legacy = {"old_email_code": "12345", "new_email_code": "67890", "new_email": "other@example.test"}
        self.assertTrue(verify_email_change_codes(legacy, "12345", "67890"))
        self.assertTrue(email_change_expired(legacy, legacy_expires_at=timezone.now() - timedelta(seconds=1)))
        self.assertFalse(email_change_expired(legacy, legacy_expires_at=timezone.now() + timedelta(minutes=2)))


class IdentityModelProtectionTests(TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "TOWNLIT_DP_FERNET_KEYS_JSON": json.dumps({"dev_1": Fernet.generate_key().decode()}),
            "TOWNLIT_DP_ACTIVE_KEY_ID": "dev_1",
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        User = get_user_model()
        self.user = User.objects.create_user(
            email="identity-wave-test@example.test",
            password="Test-only-StrongPassword123!",
            username="identitywavetest",
        )

    def test_new_identity_payload_and_notes_are_encrypted(self):
        from apps.accounts.models.identity import IdentityVerification
        iv = IdentityVerification.objects.create(
            user=self.user, method="provider", level="basic", status="pending",
            notes="Private note", provider_payload={"token": "Sensitive test payload"},
        )
        self.assertIn("tdp1:", iv.notes_encrypted)
        self.assertIn("tdp1:", iv.provider_payload_encrypted)
        loaded = IdentityVerification.objects.get(pk=iv.pk)
        self.assertEqual(loaded.notes, "Private note")
        self.assertEqual(loaded.provider_payload, {"token": "Sensitive test payload"})

    def test_update_fields_writes_shadow(self):
        from apps.accounts.models.identity import IdentityVerification
        iv = IdentityVerification.objects.create(
            user=self.user, method="provider", level="basic", status="pending"
        )
        iv.notes = "A changed note"
        iv.save(update_fields=["notes", "updated_at"])
        loaded = IdentityVerification.objects.get(pk=iv.pk)
        self.assertEqual(loaded.notes, "A changed note")
        self.assertIn("tdp1:", loaded.notes_encrypted)


class PublicAndAdminExposureTests(SimpleTestCase):
    def test_public_user_serializer_omits_birthday(self):
        from apps.accounts.serializers.user_serializers import PublicCustomUserSerializer
        self.assertNotIn("birthday", PublicCustomUserSerializer.Meta.fields)

    def test_user_admin_does_not_render_secret_verifiers(self):
        from apps.accounts.admin.user_admin import CustomUserAdmin
        fields = [name for _, section in CustomUserAdmin.fieldsets for name in section["fields"]]
        self.assertNotIn("email_change_tokens", fields)
        self.assertNotIn("access_pin", fields)
        self.assertNotIn("delete_pin", fields)
