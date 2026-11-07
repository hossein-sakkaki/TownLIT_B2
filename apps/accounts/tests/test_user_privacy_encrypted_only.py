# apps/accounts/tests/test_user_privacy_encrypted_only.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

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
from apps.accounts.serializers.user_serializers import CustomUserSerializer
from apps.core.crypto.field_protection import FieldProtectionIntegrityError


class Phase4EncryptedOnlyTests(TestCase):
    def setUp(self):
        self.patcher = patch.dict(os.environ, {
            "TOWNLIT_DP_FERNET_KEYS_JSON": json.dumps({"dev_1": Fernet.generate_key().decode()}),
            "TOWNLIT_DP_ACTIVE_KEY_ID": "dev_1",
        })
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        User = get_user_model()
        self.user = User.objects.create_user(
            email="phase4b@example.test", username="phase4btest",
            birthday=date(1991, 4, 5), password="TestingOnlyPassword123!"
        )

    def test_user_birthday_encrypted_only_and_owner_serializer(self):
        User = get_user_model()
        names = {f.name for f in User._meta.concrete_fields}
        self.assertNotIn("birthday", names)
        self.assertIn("birthday_encrypted", names)
        self.user.refresh_from_db()
        self.assertEqual(self.user.birthday, date(1991, 4, 5))
        self.assertTrue(self.user.birthday_encrypted.startswith("tdp1:"))
        self.assertIn("birthday_encrypted", CustomUserSerializer.Meta.exclude)
        # Explicit serializer field remains the owner's public API contract.
        self.assertIn("birthday", CustomUserSerializer().fields)
        self.assertNotIn("birthday_encrypted", CustomUserSerializer().fields)
        self.user.birthday = date(1994, 2, 3)
        self.user.save(update_fields=["birthday"])
        self.user.refresh_from_db()
        self.assertEqual(self.user.birthday, date(1994, 2, 3))

    def test_identity_audit_and_grant_encrypted_only(self):
        grant = IdentityGrant.objects.create(user=self.user, level="basic",
                                             source="system", reason="Sensitive")
        audit = IdentityAuditLog.objects.create(user=self.user, action="verified",
                                                source="system", reason="Private",
                                                metadata={"note": "محرمانه"})
        self.assertEqual(IdentityGrant.objects.get(pk=grant.pk).reason, "Sensitive")
        self.assertEqual(IdentityAuditLog.objects.get(pk=audit.pk).metadata, {"note": "محرمانه"})
        self.assertTrue(grant.reason_encrypted.startswith("tdp1:"))
        self.assertTrue(audit.metadata_encrypted.startswith("tdp1:"))
        self.assertFalse(any(f.name == "metadata" for f in IdentityAuditLog._meta.concrete_fields))
        self.assertFalse(any(f.name == "reason" for f in IdentityGrant._meta.concrete_fields))

    def test_tamper_and_cross_row_binding(self):
        User = get_user_model()
        another = User.objects.create_user(email="phase4second@example.test",
                                            username="phase4second", birthday=date(1990, 1, 1),
                                            password="TestingOnlyPassword123!")
        User._base_manager.filter(pk=another.pk).update(
            birthday_encrypted=self.user.birthday_encrypted
        )
        another.refresh_from_db()
        with self.assertRaises(FieldProtectionIntegrityError):
            _ = another.birthday
        with self.assertRaises(ValueError):
            User.objects.filter(pk=self.user.pk).update(birthday_encrypted="plaintext")
        with self.assertRaises(ValueError):
            User.objects.bulk_create([User(email="bulk@example.test")])

    def test_admin_restricted_fieldsets(self):
        from types import SimpleNamespace
        from django.contrib.admin.sites import AdminSite
        from apps.accounts.admin.user_admin import CustomUserAdmin
        from apps.accounts.admin.identity_admin import IdentityGrantAdmin
        user_admin = CustomUserAdmin(type(self.user), AdminSite())
        grant_admin = IdentityGrantAdmin(IdentityGrant, AdminSite())
        staff = SimpleNamespace(user=SimpleNamespace(is_superuser=False))
        user_fields = str(user_admin.get_fieldsets(staff, self.user))
        grant_fields = str(grant_admin.get_fieldsets(staff, None))
        self.assertIn("birthday_masked", user_fields)
        self.assertNotIn('"birthday"', user_fields)
        self.assertIn("reason_masked", grant_fields)

    def test_integrity_command(self):
        out = StringIO()
        call_command("verify_user_privacy_wave", stdout=out)
        self.assertIn("errors=0", out.getvalue())
