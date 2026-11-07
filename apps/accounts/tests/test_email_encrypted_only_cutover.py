# apps/accounts/tests/test_email_encrypted_only_cutover.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Regressions for CustomUser email encrypted-only storage and Django auth."""

import base64
import json
import os
from io import StringIO
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.core.exceptions import FieldDoesNotExist
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.forms import (
    UserChangeForm, UserChangeRestrictedForm, UserCreationForm,
    UserCreationRestrictedForm,
)
from apps.accounts.serializers.user_serializers import (
    CustomUserSerializer, PublicCustomUserSerializer,
)
from apps.accounts.services.contact_protection import index_matches
from apps.accounts.services.email_lookup import user_email_q
from apps.core.crypto.field_protection import FieldProtectionIntegrityError


class EmailEncryptedOnlyCutoverTests(TestCase):
    def setUp(self):
        self.keys = patch.dict(os.environ, {
            "TOWNLIT_DP_FERNET_KEYS_JSON": json.dumps({
                "dev_1": Fernet.generate_key().decode(),
            }),
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
            email="CUTOvER@Example.test", username="emailcutover",
            password="StrongDevOnly123!", primary_language="en",
        )
        self.user.is_active = True
        self.user.save(update_fields=["is_active"])

    def test_email_is_property_not_database_column(self):
        with self.assertRaises(FieldDoesNotExist):
            self.User._meta.get_field("email")
        self.assertEqual(self.User.USERNAME_FIELD, "username")
        fields = {f.name for f in self.User._meta.concrete_fields}
        self.assertIn("email_encrypted", fields)
        self.assertIn("email_blind_index", fields)
        self.assertNotIn("email", fields)
        self.assertTrue(self.user.email_encrypted.startswith("tdp1:"))
        self.assertNotIn("example.test", self.user.email_encrypted)

    def test_login_works_with_both_identifiers(self):
        backend = ModelBackend()
        for identifier in ("emailcutover", "EMAILCUTOVER", "cutover@example.test"):
            self.assertEqual(
                backend.authenticate(None, username=identifier, password="StrongDevOnly123!").pk,
                self.user.pk,
            )
        self.assertIsNone(backend.authenticate(
            None, username="cutover@example.test", password="WrongPassword123!",
        ))

    def test_save_update_fields_reindexes_and_old_address_fails(self):
        original = self.user.email_blind_index
        self.user.email = "next-cutover@example.test"
        self.user.save(update_fields=["email"])
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "next-cutover@example.test")
        self.assertNotEqual(self.user.email_blind_index, original)
        self.assertTrue(index_matches(self.user.email_blind_index, self.user.email, field="email"))
        self.assertFalse(self.User.objects.filter(user_email_q("cutover@example.test")).exists())
        self.assertEqual(self.User.objects.get(user_email_q("next-cutover@example.test")).pk, self.user.pk)

    def test_casefolded_email_uniqueness_is_database_enforced(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.User.objects.create_user(
                    email="cutover@EXAMPLE.TEST", username="anothercutover",
                    password="StrongDevOnly123!",
                )
        self.assertEqual(self.User.objects.filter(user_email_q("cutover@example.test")).count(), 1)

    def test_missing_row_email_is_not_returned_as_plaintext_or_empty(self):
        self.User._base_manager.filter(pk=self.user.pk).update(email_encrypted=None)
        self.user.refresh_from_db()
        with self.assertRaises(FieldProtectionIntegrityError):
            _ = self.user.email

    def test_owner_and_public_serializers_keep_safe_contract(self):
        owner = CustomUserSerializer(self.user).data
        self.assertEqual(owner["email"], self.user.email)
        self.assertNotIn("email_encrypted", owner)
        self.assertNotIn("email_blind_index", owner)
        public = PublicCustomUserSerializer(self.user).data
        self.assertNotIn("email", public)
        self.user.show_email = True
        self.user.save(update_fields=["show_email"])
        self.assertEqual(PublicCustomUserSerializer(self.user).data["email"], self.user.email)

    def test_admin_create_forms_set_logical_email_property(self):
        for form_type in (UserCreationForm, UserCreationRestrictedForm):
            user = self.User(username="formcreated")
            form = form_type(data={"email":"form-created@example.test", "password":"StrongDevOnly123!"}, instance=user)
            self.assertTrue(form.is_valid(), form.errors)
            created = form.save()
            self.assertEqual(created.email, "form-created@example.test")
            created.delete()

    def test_edit_form_disabled_email_is_initialized(self):
        for form_type in (UserChangeForm, UserChangeRestrictedForm):
            form = form_type(instance=self.user)
            self.assertEqual(form.fields["email"].initial, self.user.email)
            self.assertTrue(form.fields["email"].disabled)

    def test_cli_createsuperuser_uses_email_argument_with_no_plaintext_field(self):
        out = StringIO()
        with patch.dict(os.environ, {"DJANGO_SUPERUSER_PASSWORD": "StrongDevOnly123!"}):
            call_command("createsuperuser", username="cliperson", email="cli.person@example.test",
                         interactive=False, stdout=out)
        created = self.User.objects.get(username="cliperson")
        self.assertTrue(created.is_superuser)
        self.assertEqual(created.email, "cli.person@example.test")
        self.assertNotIn("cli.person@example.test", out.getvalue())

    def test_readiness_verifier_indicates_encrypted_only(self):
        out = StringIO()
        call_command("verify_email_cutover_readiness", stdout=out)
        self.assertIn("email_storage=encrypted_only", out.getvalue())
        self.assertIn("errors=0", out.getvalue())
