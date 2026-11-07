# apps/accounts/tests/test_user_admin_protected_email.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Regressions for admin change/add forms with encrypted-only email."""

import base64
import json
import os
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.accounts.admin.user_admin import CustomUserAdmin


class UserAdminProtectedEmailTests(TestCase):
    def setUp(self):
        self.keys = patch.dict(os.environ, {
            "TOWNLIT_DP_FERNET_KEYS_JSON": json.dumps({
                "test_1": Fernet.generate_key().decode(),
            }),
            "TOWNLIT_DP_ACTIVE_KEY_ID": "test_1",
            "TOWNLIT_DP_BLIND_INDEX_KEYS_JSON": json.dumps({
                "test_bi_1": base64.urlsafe_b64encode(os.urandom(32)).decode(),
            }),
            "TOWNLIT_DP_BLIND_INDEX_ACTIVE_KEY_ID": "test_bi_1",
        })
        self.keys.start()
        self.addCleanup(self.keys.stop)
        self.User = get_user_model()
        self.superuser = self.User.objects.create_superuser(
            email="admin@example.test", username="adminemailfix",
            password="TestOnlyStrong123!",
        )
        self.staff = self.User.objects.create_user(
            email="staff@example.test", username="staffemailfix",
            password="TestOnlyStrong123!",
        )
        self.staff.is_active = True
        self.staff.is_admin = True
        self.staff.save(update_fields=["is_active", "is_admin"])
        self.target = self.User.objects.create_user(
            email="target@example.test", username="targetemailfix",
            password="TestOnlyStrong123!",
        )
        self.admin = CustomUserAdmin(self.User, AdminSite())
        self.factory = RequestFactory()

    def _request(self, user):
        request = self.factory.get("/admin/accounts/customuser/")
        request.user = user
        return request

    def test_superuser_change_form_disables_email_and_displays_property(self):
        request = self._request(self.superuser)
        form_type = self.admin.get_form(request, obj=self.target)
        form = form_type(instance=self.target)
        # The declared email form field is retained for compatibility, but
        # must remain disabled; admin displays the property separately.
        self.assertIn("email", form.fields)
        self.assertTrue(form.fields["email"].disabled)
        self.assertEqual(form.fields["email"].initial, "target@example.test")
        fieldsets = self.admin.get_fieldsets(request, self.target)
        self.assertIn("email_display", str(fieldsets))
        self.assertNotIn("email", [field for _, opts in fieldsets for field in opts["fields"]])
        self.assertEqual(self.admin.email_display(self.target), "target@example.test")
        self.assertEqual(self.target.email, "target@example.test")

    def test_staff_change_form_disables_email_and_preserves_masked_fields(self):
        request = self._request(self.staff)
        form_type = self.admin.get_form(request, obj=self.target)
        form = form_type(instance=self.target)
        self.assertIn("email", form.fields)
        self.assertTrue(form.fields["email"].disabled)
        self.assertEqual(form.fields["email"].initial, "target@example.test")
        fieldsets = self.admin.get_fieldsets(request, self.target)
        self.assertIn("email_display", str(fieldsets))
        self.assertNotIn("email", [field for _, opts in fieldsets for field in opts["fields"]])
        self.assertIn("birthday_masked", str(fieldsets))
        self.assertIn("mobile_masked", str(fieldsets))

    def test_add_form_still_accepts_email_input(self):
        for user in (self.superuser, self.staff):
            request = self._request(user)
            form_type = self.admin.get_form(request, obj=None)
            self.assertIn("email", form_type.base_fields)
            self.assertTrue(form_type.base_fields["email"].required)
            self.assertNotIn("email_display", str(self.admin.get_fieldsets(request, None)))

    def test_actual_admin_change_page_get_for_superuser(self):
        self.client.force_login(self.superuser)
        url = reverse("admin:accounts_customuser_change", args=(self.target.pk,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "target@example.test")
