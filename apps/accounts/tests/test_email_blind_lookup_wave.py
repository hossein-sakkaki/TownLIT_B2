# apps/accounts/tests/test_email_blind_lookup_wave.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Regression for encrypted shadow email / blind-index-first read routing."""

import base64
import json
import os
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.serializers.auth_serializers import RegisterUserSerializer
from apps.accounts.services.email_lookup import (
    user_email_index,
    user_email_q,
    user_identifier_q,
)


class EmailBlindLookupWaveTests(TestCase):
    def setUp(self):
        self.patcher = patch.dict(os.environ, {
            "TOWNLIT_DP_FERNET_KEYS_JSON": json.dumps({"dev_1": Fernet.generate_key().decode()}),
            "TOWNLIT_DP_ACTIVE_KEY_ID": "dev_1",
            "TOWNLIT_DP_BLIND_INDEX_KEYS_JSON": json.dumps({
                "dev_bi_1": base64.urlsafe_b64encode(os.urandom(32)).decode(),
            }),
            "TOWNLIT_DP_BLIND_INDEX_ACTIVE_KEY_ID": "dev_bi_1",
        })
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            email="Mixed.Email@Example.TEST",
            username="mixedemail",
            password="ExamplePass123!",
        )
        self.user.is_active = True
        self.user.save(update_fields=["is_active"])

    def test_email_equality_uses_blind_index_and_normalizes_case(self):
        self.assertEqual(
            self.User.objects.get(user_email_q("  mixed.email@example.test ")).pk,
            self.user.pk,
        )
        self.assertEqual(
            user_email_index("MIXED.EMAIL@example.TEST"),
            self.user.email_blind_index,
        )

    def test_blank_email_fails_closed_even_when_other_users_have_null_index(self):
        self.User.objects.filter(pk=self.user.pk).exists()
        self.assertFalse(self.User.objects.filter(user_email_q("")).exists())
        self.assertFalse(self.User.objects.filter(user_email_q(None)).exists())

    def test_username_and_email_identifiers_resolve_without_plaintext_filter(self):
        self.assertEqual(
            self.User.objects.get(user_identifier_q("MIXEDEMAIL")).pk,
            self.user.pk,
        )
        self.assertEqual(
            self.User.objects.get(user_identifier_q("mixed.email@example.test")).pk,
            self.user.pk,
        )
        self.assertFalse(self.User.objects.filter(user_identifier_q("not-found")).exists())

    def test_email_update_fields_reindexes_and_old_email_stops_matching(self):
        self.user.email = "Second@Example.test"
        self.user.save(update_fields=["email"])
        self.user.refresh_from_db()
        self.assertEqual(self.User.objects.get(user_email_q("second@example.test")).pk, self.user.pk)
        self.assertFalse(self.User.objects.filter(user_email_q("mixed.email@example.test")).exists())

    def test_registration_duplicate_uses_case_independent_blind_lookup(self):
        data = {"email": "MIXED.EMAIL@example.test", "password": "ExamplePass123!", "agree_to_terms": True}
        serializer = RegisterUserSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("email", serializer.errors)

    def test_missing_hmac_key_fails_closed_without_plaintext_fallback(self):
        from apps.core.crypto.blind_index import BlindIndexConfigError
        with patch.dict(os.environ, {"TOWNLIT_DP_BLIND_INDEX_KEYS_JSON": ""}):
            with self.assertRaises(BlindIndexConfigError):
                user_email_q("mixed.email@example.test")

    def test_email_search_in_social_context_respects_visibility(self):
        query = user_email_q("mixed.email@example.test")
        self.assertFalse(self.User.objects.filter(query, show_email=True).exists())
        self.user.show_email = True
        self.user.save(update_fields=["show_email"])
        self.assertTrue(self.User.objects.filter(query, show_email=True).exists())
