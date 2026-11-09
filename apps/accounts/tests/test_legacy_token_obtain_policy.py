# apps/accounts/tests/test_legacy_token_obtain_policy.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-05.
# Last Update by Hossein Sakkaki on 2026-11-09.
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

    def _issue(self, password="ExistingPassword42!", identifier="email"):
        return self.client.post(
            self.url,
            data={identifier: self.user.email, "password": password},
            content_type="application/json",
        )

    def _assert_no_tokens(self, response):
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("access", response.data)
        self.assertNotIn("refresh", response.data)

    def test_non_2fa_active_user_retains_legacy_compatibility(self):
        for identifier in ("email", "username"):
            with self.subTest(identifier=identifier):
                response = self._issue(identifier=identifier)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.data["access"])
                self.assertTrue(response.data["refresh"])

    def test_2fa_account_cannot_obtain_jwt_from_password_alone(self):
        self.user.two_factor_enabled = True
        self.user.save(update_fields=["two_factor_enabled"])
        for identifier in ("email", "username"):
            with self.subTest(identifier=identifier):
                self._assert_no_tokens(self._issue(identifier=identifier))

    def test_deleted_account_cannot_use_generic_token_route(self):
        self.user.is_deleted = True
        self.user.save(update_fields=["is_deleted"])
        for identifier in ("email", "username"):
            with self.subTest(identifier=identifier):
                self._assert_no_tokens(self._issue(identifier=identifier))

    def test_suspended_account_cannot_use_generic_token_route(self):
        self.user.is_suspended = True
        self.user.save(update_fields=["is_suspended"])
        for identifier in ("email", "username"):
            with self.subTest(identifier=identifier):
                self._assert_no_tokens(self._issue(identifier=identifier))

    def test_invalid_password_does_not_issue_jwt(self):
        for identifier in ("email", "username"):
            with self.subTest(identifier=identifier):
                self._assert_no_tokens(
                    self._issue(password="WrongPassword42!", identifier=identifier)
                )

    def test_concrete_username_authentication_remains_available(self):
        response = self.client.post(
            self.url,
            data={"username": self.user.username, "password": "ExistingPassword42!"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["access"])
        self.assertTrue(response.data["refresh"])
