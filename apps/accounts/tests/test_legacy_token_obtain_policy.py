# apps/accounts/tests/test_legacy_token_obtain_policy.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-05.
# Last Update by Hossein Sakkaki on 2026-11-05.
#

"""Ensure the generic JWT issuance route cannot bypass TownLIT 2FA."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class LegacyTokenObtainPolicyTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="legacy-token-policy@example.com",
            username="legacy_token_policy",
            password="ExistingPassword42!",
        )
        self.user.is_active = True
        self.user.save(update_fields=["is_active"])
        self.url = reverse("token_obtain_pair")

    def _issue(self, password="ExistingPassword42!"):
        return self.client.post(
            self.url,
            data={"email": self.user.email, "password": password},
            content_type="application/json",
        )

    def _assert_no_tokens(self, response):
        self.assertNotEqual(response.status_code, 200)
        self.assertNotIn("access", response.data)
        self.assertNotIn("refresh", response.data)

    def test_non_2fa_active_user_retains_legacy_compatibility(self):
        response = self._issue()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["access"])
        self.assertTrue(response.data["refresh"])

    def test_2fa_account_cannot_obtain_jwt_from_password_alone(self):
        self.user.two_factor_enabled = True
        self.user.save(update_fields=["two_factor_enabled"])
        self._assert_no_tokens(self._issue())

    def test_deleted_account_cannot_use_generic_token_route(self):
        self.user.is_deleted = True
        self.user.save(update_fields=["is_deleted"])
        self._assert_no_tokens(self._issue())

    def test_suspended_account_cannot_use_generic_token_route(self):
        self.user.is_suspended = True
        self.user.save(update_fields=["is_suspended"])
        self._assert_no_tokens(self._issue())

    def test_invalid_password_does_not_issue_jwt(self):
        self._assert_no_tokens(self._issue(password="WrongPassword42!"))
