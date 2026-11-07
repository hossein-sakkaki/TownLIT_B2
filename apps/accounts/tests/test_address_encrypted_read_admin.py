# apps/accounts/tests/test_address_encrypted_read_admin.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

import json
import os
from types import SimpleNamespace
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase

from apps.accounts.admin.address_admin import AddressAdmin
from apps.accounts.models import Address


class AddressAdminCompatibilityTests(TestCase):
    def test_staff_mask_and_superuser_reveal(self):
        with patch.dict(os.environ, {
            "TOWNLIT_DP_FERNET_KEYS_JSON": json.dumps({"dev_1": Fernet.generate_key().decode()}),
            "TOWNLIT_DP_ACTIVE_KEY_ID": "dev_1",
        }):
            a = Address.objects.create(additional="Confidential")
            admin = AddressAdmin(Address, AdminSite())
            staff = RequestFactory().get("/admin/")
            staff.user = SimpleNamespace(is_staff=True, is_superuser=False)
            root = RequestFactory().get("/admin/")
            root.user = SimpleNamespace(is_staff=True, is_superuser=True)
            self.assertEqual(admin.additional_masked(a), "Protected — superuser access required")
            self.assertEqual(admin.additional_revealed(a), "Confidential")
            self.assertNotIn("additional", admin.get_fields(staff, a))
            self.assertNotIn("additional_encrypted", admin.get_fields(root, a))
            self.assertNotIn("Confidential", str(a))
