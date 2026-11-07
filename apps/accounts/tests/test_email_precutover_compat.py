# apps/accounts/tests/test_email_precutover_compat.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Precutover regressions for email read/write boundaries and ORM compatibility."""

import base64
import json
import os
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.core.management import call_command
from django.test import TestCase

from apps.accounts.forms import (
    UserChangeForm,
    UserChangeRestrictedForm,
    UserCreationForm,
    UserCreationRestrictedForm,
)
from apps.accounts.serializers.user_serializers import CustomUserSerializer
from apps.bookstore_inventory.forms.warehouse import eligible_warehouse_staff_users
from apps.conversation.services.boundary_access import group_boundary_conflict_for_add


class EmailPrecutoverCompatibilityTests(TestCase):
    def setUp(self):
        self.key_patch = patch.dict(os.environ, {
            "TOWNLIT_DP_FERNET_KEYS_JSON": json.dumps({"dev_1": Fernet.generate_key().decode()}),
            "TOWNLIT_DP_ACTIVE_KEY_ID": "dev_1",
            "TOWNLIT_DP_BLIND_INDEX_KEYS_JSON": json.dumps({
                "dev_bi_1": base64.urlsafe_b64encode(os.urandom(32)).decode(),
            }),
            "TOWNLIT_DP_BLIND_INDEX_ACTIVE_KEY_ID": "dev_bi_1",
        })
        self.key_patch.start()
        self.addCleanup(self.key_patch.stop)
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            email="Precutover@Example.TEST", username="precutover",
            primary_language="en", password="TestOnlyStrong123!",
        )
        self.user.is_active = True
        self.user.save(update_fields=["is_active"])

    def test_django_backend_accepts_username_and_email(self):
        backend = ModelBackend()
        for identifier in ("precutover", "PRECUTOVER", "PRECUTOVER@example.test"):
            result = backend.authenticate(None, username=identifier, password="TestOnlyStrong123!")
            self.assertIsNotNone(result)
            self.assertEqual(result.pk, self.user.pk)

    def test_owner_serializer_displays_but_never_updates_email(self):
        self.assertEqual(CustomUserSerializer(self.user).data["email"], self.user.email)
        serializer = CustomUserSerializer(
            self.user, data={"email": "not-verified@example.test"}, partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertNotIn("email", serializer.validated_data)

    def test_admin_forms_explicitly_declare_email_field(self):
        for form in (UserCreationForm, UserChangeForm, UserCreationRestrictedForm, UserChangeRestrictedForm):
            self.assertIn("email", form.base_fields)
        self.assertTrue(UserChangeForm.base_fields["email"].disabled)
        self.assertTrue(UserChangeRestrictedForm.base_fields["email"].disabled)

    def test_warehouse_staff_queryset_does_not_sort_by_db_email(self):
        self.user.is_admin = True
        self.user.save(update_fields=["is_admin"])
        qs = eligible_warehouse_staff_users()
        self.assertEqual(qs.query.order_by, ("family", "name", "username", "pk"))
        self.assertIn(self.user.pk, list(qs.values_list("pk", flat=True)))

    def test_group_boundary_does_not_select_concrete_email_column(self):
        participants = Mock()
        participants.exclude.return_value.only.return_value = []
        dialogue = SimpleNamespace(is_group=True, participants=participants)
        self.assertIsNone(group_boundary_conflict_for_add(dialogue=dialogue, target_user=self.user))
        participants.exclude.return_value.only.assert_called_once_with("id", "username")

    def test_readiness_verifier_checks_encrypted_email_without_exposing_pii(self):
        out = StringIO()
        call_command("verify_email_cutover_readiness", stdout=out)
        result = out.getvalue()
        self.assertIn("rows=1 email_verified=1 missing_username=0 errors=0", result)
        self.assertIn("schema_cutover_authorized=no", result)
        self.assertNotIn("Precutover@Example.TEST", result)
