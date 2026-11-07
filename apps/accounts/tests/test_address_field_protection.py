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
from apps.core.crypto.field_protection import FieldProtector


class AddressCompatibilityStageTests(TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "TOWNLIT_DP_FERNET_KEYS_JSON": json.dumps({"dev_1": Fernet.generate_key().decode()}),
            "TOWNLIT_DP_ACTIVE_KEY_ID": "dev_1",
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_writes_are_encrypted_without_feature_flags(self):
        a = Address.objects.create(additional="Floor 2 • طبقه دوم")
        self.assertEqual(a.additional, "Floor 2 • طبقه دوم")
        self.assertEqual(AddressSerializer(a).data["additional"], a.additional)
        self.assertNotIn("additional_encrypted", AddressSerializer(a).data)
        self.assertTrue(a.additional_encrypted.startswith("tdp1:dev_1:"))
        a.additional = "Door B"
        a.save(update_fields=["additional"])
        a.refresh_from_db()
        self.assertEqual(a.additional_for_read(), "Door B")

    def test_backfill_requires_apply_and_verifies(self):
        a = Address.objects.create(additional="Legacy")
        Address._base_manager.filter(pk=a.pk).update(additional_encrypted=None)
        with override_settings(DEBUG=True):
            call_command("backfill_address_additional_encrypted", stdout=StringIO())
            a.refresh_from_db()
            self.assertIsNone(a.additional_encrypted)
            call_command("backfill_address_additional_encrypted", "--apply", stdout=StringIO())
            call_command("backfill_address_additional_encrypted", "--verify-only", stdout=StringIO())
        a.refresh_from_db()
        self.assertEqual(a.additional_for_read(), "Legacy")

    def test_null_and_empty_preserved(self):
        a = Address.objects.create(additional=None)
        b = Address.objects.create(additional="")
        self.assertIsNone(a.additional_encrypted)
        self.assertEqual(b.additional_for_read(), "")

    def test_bulk_write_bypass_is_blocked(self):
        a = Address.objects.create(additional="Private")
        with self.assertRaises(ValueError):
            Address.objects.filter(pk=a.pk).update(additional="raw")
        with self.assertRaises(ValueError):
            Address.objects.bulk_create([Address(additional="raw")])

    def test_read_does_not_fallback_if_ciphertext_is_invalid(self):
        a = Address.objects.create(additional="Private")
        Address._base_manager.filter(pk=a.pk).update(additional_encrypted="damaged")
        a.refresh_from_db()
        with self.assertRaises(Exception):
            a.additional_for_read()
