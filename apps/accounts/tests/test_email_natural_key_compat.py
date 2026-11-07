# apps/accounts/tests/test_email_natural_key_compat.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Precutover compatibility for Django ModelBackend and email blind indexes."""

import base64
import json
import os
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.test import TestCase

from apps.core.crypto.blind_index import BlindIndexConfigError


class EmailNaturalKeyCompatibilityTests(TestCase):
    def setUp(self):
        self.keys = patch.dict(os.environ, {
            "TOWNLIT_DP_FERNET_KEYS_JSON": json.dumps({"dev_1": Fernet.generate_key().decode()}),
            "TOWNLIT_DP_ACTIVE_KEY_ID": "dev_1",
            "TOWNLIT_DP_BLIND_INDEX_KEYS_JSON": json.dumps({
                "dev_bi_1": base64.urlsafe_b64encode(os.urandom(32)).decode(),
            }),
            "TOWNLIT_DP_BLIND_INDEX_ACTIVE_KEY_ID": "dev_bi_1",
        })
        self.keys.start()
        self.addCleanup(self.keys.stop)
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            email="Mixed.Account@Example.TEST",
            username="accountmixed",
            password="StrongDevOnly123!",
        )
        self.user.is_active = True
        self.user.save(update_fields=["is_active"])

    def test_natural_key_resolves_case_insensitive_email(self):
        matched = self.User.objects.get_by_natural_key("mixed.account@example.test")
        self.assertEqual(matched.pk, self.user.pk)

    def test_standard_django_backend_authenticates_via_blind_index(self):
        matched = ModelBackend().authenticate(
            request=None,
            username="MIXED.ACCOUNT@example.test",
            password="StrongDevOnly123!",
        )
        self.assertEqual(matched.pk, self.user.pk)

    def test_wrong_password_is_rejected(self):
        self.assertIsNone(ModelBackend().authenticate(
            request=None,
            username="mixed.account@example.test",
            password="IncorrectPassword123!",
        ))

    def test_email_change_invalidates_previous_natural_key(self):
        self.user.email = "New.Account@Example.TEST"
        self.user.save(update_fields=["email"])
        self.assertEqual(
            self.User.objects.get_by_natural_key("new.account@example.test").pk,
            self.user.pk,
        )
        with self.assertRaises(self.User.DoesNotExist):
            self.User.objects.get_by_natural_key("mixed.account@example.test")

    def test_missing_blind_index_keys_never_reverts_to_plaintext(self):
        with patch.dict(os.environ, {"TOWNLIT_DP_BLIND_INDEX_KEYS_JSON": ""}):
            with self.assertRaises(BlindIndexConfigError):
                self.User.objects.get_by_natural_key("mixed.account@example.test")
