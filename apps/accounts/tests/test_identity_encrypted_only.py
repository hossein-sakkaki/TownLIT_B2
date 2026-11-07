# apps/accounts/tests/test_identity_encrypted_only.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

import json
import os
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.test import SimpleTestCase

from apps.accounts.models.identity import IdentityVerification
from apps.accounts.serializers.identity_serializers import IdentityStatusSerializer


class IdentityEncryptedOnlyContractTests(SimpleTestCase):
    def test_sensitive_legacy_columns_removed(self):
        column_names = {field.name for field in IdentityVerification._meta.local_fields}
        self.assertNotIn("notes", column_names)
        self.assertNotIn("provider_payload", column_names)
        self.assertIn("notes_encrypted", column_names)
        self.assertIn("provider_payload_encrypted", column_names)

    def test_public_identity_status_does_not_include_private_fields(self):
        fields = set(IdentityStatusSerializer.Meta.fields)
        self.assertNotIn("provider_payload_encrypted", fields)
        self.assertNotIn("notes_encrypted", fields)
        self.assertNotIn("provider_reference", fields)
