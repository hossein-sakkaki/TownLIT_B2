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


