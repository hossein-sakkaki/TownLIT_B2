# apps/accounts/tests/test_address_field_protection.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

import json
import os
from io import StringIO
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.accounts.models import Address
from apps.accounts.serializers.address_serializers import AddressSerializer
from apps.core.crypto.field_protection import FieldProtectionIntegrityError, FieldProtectionUnavailable


class AddressEncryptedOnlyTests(TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "TOWNLIT_DP_FERNET_KEYS_JSON": json.dumps({"dev_1": Fernet.generate_key().decode()}),
            "TOWNLIT_DP_ACTIVE_KEY_ID": "dev_1",
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_create_update_and_serializer_contract(self):
        a = Address.objects.create(additional="Unit 4 • طبقه ۲")
        self.assertEqual(a.additional, "Unit 4 • طبقه ۲")
        a.refresh_from_db()
        self.assertEqual(a.additional, "Unit 4 • طبقه ۲")
        self.assertEqual(AddressSerializer(a).data["additional"], "Unit 4 • طبقه ۲")
        self.assertNotIn("additional_encrypted", AddressSerializer(a).data)
        self.assertTrue(a.additional_encrypted.startswith("tdp1:dev_1:"))
        self.assertTrue(AddressSerializer(data={"additional": "B"}).is_valid())
        a.additional = "New note"
        a.save(update_fields=["additional"])
        a.refresh_from_db()
        self.assertEqual(a.additional, "New note")

    def test_serializer_create_and_null_empty(self):
        serializer = AddressSerializer(data={"additional": "From API"})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        obj = serializer.save()
        self.assertEqual(obj.additional, "From API")
        self.assertEqual(Address.objects.get(pk=obj.pk).additional, "From API")
        self.assertIsNone(Address.objects.create(additional=None).additional)
        self.assertEqual(Address.objects.create(additional="").additional, "")

    def test_encrypted_only_and_bulk_write_protection(self):
        self.assertNotIn("additional", [f.name for f in Address._meta.concrete_fields])
        a = Address.objects.create(additional="Private")
        with self.assertRaises(ValueError):
            Address.objects.filter(pk=a.pk).update(additional_encrypted="raw")
        with self.assertRaises(ValueError):
            Address.objects.bulk_create([Address(additional="raw")])

    def test_tampering_does_not_fallback(self):
        a = Address.objects.create(additional="Protected")
        Address._base_manager.filter(pk=a.pk).update(additional_encrypted="not-an-envelope")
        a.refresh_from_db()
        with self.assertRaises(FieldProtectionIntegrityError):
            _ = a.additional

    def test_missing_key_does_not_fallback(self):
        a = Address.objects.create(additional="Protected")
        a.refresh_from_db()
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(FieldProtectionUnavailable):
                _ = a.additional

    def test_dev_integrity_command(self):
        a = Address.objects.create(additional="Protected")
        with override_settings(DEBUG=True):
            out = StringIO()
            call_command("verify_address_additional_encrypted", stdout=out)
            self.assertIn("errors=0", out.getvalue())
            self.assertNotIn("Protected", out.getvalue())
