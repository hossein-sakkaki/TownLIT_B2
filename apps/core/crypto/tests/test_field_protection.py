# apps/core/crypto/tests/test_field_protection.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

import json
import os
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet

from apps.core.crypto.field_protection import (
    FieldProtector,
    FieldProtectionConfigError,
    FieldProtectionIntegrityError,
    FieldProtectionUnavailable,
)


FIELD = "accounts.Address.additional"


class FieldProtectorTests(unittest.TestCase):
    def setUp(self):
        self.key1 = Fernet.generate_key().decode("ascii")
        self.key2 = Fernet.generate_key().decode("ascii")
        self.protector = FieldProtector(keys={"v1": self.key1}, active_key_id="v1")

    def test_round_trip_and_randomization(self):
        value = "Apartment 4B • زنگ دوم • 你好"
        first = self.protector.protect(value, field=FIELD, row_id=42)
        second = self.protector.protect(value, field=FIELD, row_id=42)
        self.assertNotEqual(first, second)
        self.assertNotIn(value, first)
        self.assertEqual(self.protector.reveal(first, field=FIELD, row_id=42), value)

    def test_null_and_empty_are_distinct(self):
        self.assertIsNone(self.protector.protect(None, field=FIELD, row_id=1))
        self.assertIsNone(self.protector.reveal(None, field=FIELD, row_id=1))
        encrypted_empty = self.protector.protect("", field=FIELD, row_id=1)
        self.assertIsNotNone(encrypted_empty)
        self.assertEqual(self.protector.reveal(encrypted_empty, field=FIELD, row_id=1), "")

    def test_rejects_swapped_row_or_field(self):
        token = self.protector.protect("private", field=FIELD, row_id=1)
        with self.assertRaises(FieldProtectionIntegrityError):
            self.protector.reveal(token, field=FIELD, row_id=2)
        with self.assertRaises(FieldProtectionIntegrityError):
            self.protector.reveal(token, field="accounts.Address.route", row_id=1)

    def test_rejects_corruption_and_unknown_format(self):
        token = self.protector.protect("private", field=FIELD, row_id=1)
        prefix, kid, encoded = token.split(":", 2)
        mutated = f"{prefix}:{kid}:{encoded[:-2]}AA"
        with self.assertRaises(FieldProtectionIntegrityError):
            self.protector.reveal(mutated, field=FIELD, row_id=1)
        with self.assertRaises(FieldProtectionIntegrityError):
            self.protector.reveal("legacy-plaintext", field=FIELD, row_id=1)

    def test_key_id_is_authenticated_even_when_two_ids_share_key(self):
        token = self.protector.protect("private", field=FIELD, row_id=1)
        aliases = FieldProtector(keys={"v1": self.key1, "v2": self.key1}, active_key_id="v2")
        forged = token.replace("tdp1:v1:", "tdp1:v2:", 1)
        with self.assertRaises(FieldProtectionIntegrityError):
            aliases.reveal(forged, field=FIELD, row_id=1)

    def test_rotation_and_missing_historical_key(self):
        old = self.protector.protect("keep forever", field=FIELD, row_id=1)
        rotated = FieldProtector(
            keys={"v1": self.key1, "v2": self.key2}, active_key_id="v2"
        )
        self.assertEqual(rotated.reveal(old, field=FIELD, row_id=1), "keep forever")
        new = rotated.rewrap(old, field=FIELD, row_id=1)
        self.assertTrue(new.startswith("tdp1:v2:"))
        self.assertEqual(rotated.reveal(new, field=FIELD, row_id=1), "keep forever")
        without_old_key = FieldProtector(keys={"v2": self.key2}, active_key_id="v2")
        with self.assertRaises(FieldProtectionUnavailable):
            without_old_key.reveal(old, field=FIELD, row_id=1)

    def test_missing_or_invalid_config_fails_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(FieldProtectionUnavailable):
                FieldProtector.from_environment()
        with self.assertRaises(FieldProtectionConfigError):
            FieldProtector(keys={"v1": "not-a-fernet-key"}, active_key_id="v1")
        env = {
            "TOWNLIT_DP_FERNET_KEYS_JSON": json.dumps({"v1": self.key1}),
            "TOWNLIT_DP_ACTIVE_KEY_ID": "v1",
        }
        with patch.dict(os.environ, env):
            self.assertEqual(
                FieldProtector.from_environment().reveal(
                    self.protector.protect("ok", field=FIELD, row_id=1),
                    field=FIELD, row_id=1,
                ),
                "ok",
            )

    def test_rejects_unpersisted_or_invalid_record_id(self):
        with self.assertRaises(ValueError):
            self.protector.protect("x", field=FIELD, row_id=0)
        with self.assertRaises(ValueError):
            self.protector.protect("x", field="../invalid", row_id=1)
