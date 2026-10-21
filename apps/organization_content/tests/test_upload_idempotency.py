# apps/organization_content/tests/test_upload_idempotency.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-19.
# Last Update by Hossein Sakkaki on 2026-10-19.

import hashlib
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from apps.organization_media.models import OrganizationMediaAsset
from apps.organization_media.services import uploads


class UploadIdempotencyTests(SimpleTestCase):
    def setUp(self):
        class Organization:
            objects = MagicMock()
        self.organization = Organization()
        self.organization.pk = 17
        self.organization.__class__.objects.select_for_update.return_value.get.return_value = self.organization
        self.actor = SimpleNamespace(pk=42)
        self.file = SimpleUploadedFile("source.jpg", b"same raw source", content_type="image/jpeg")
        self.existing = SimpleNamespace(organization_id=17, created_by_id=42, kind="image",
                                        upload_sha256=hashlib.sha256(b"same raw source").hexdigest())

    def test_digest_is_repeatable_and_restores_file_pointer(self):
        first = uploads._file_digest(self.file)
        self.assertEqual(first, uploads._file_digest(self.file))
        self.assertEqual(self.file.tell(), 0)
        self.assertEqual(first, self.existing.upload_sha256)

    @patch.object(uploads, "ensure_organization_content_writes_enabled")
    @patch.object(uploads, "ensure_content_manager")
    @patch.object(uploads, "_validate_upload")
    @patch.object(OrganizationMediaAsset, "objects")
    def test_same_identifier_and_source_reuses_original_asset(self, asset_manager, validate, permission, enabled):
        asset_manager.filter.return_value.first.return_value = self.existing
        with patch.object(uploads.transaction, "atomic", return_value=nullcontext()):
            result = uploads.create_asset(organization=self.organization, actor=self.actor,
                                           kind="image", file=self.file, public_id="same-identifier")
        self.assertIs(result, self.existing)
        validate.assert_not_called()

    @patch.object(uploads, "ensure_organization_content_writes_enabled")
    @patch.object(uploads, "ensure_content_manager")
    @patch.object(OrganizationMediaAsset, "objects")
    def test_reusing_identifier_with_different_source_is_rejected(self, asset_manager, permission, enabled):
        asset_manager.filter.return_value.first.return_value = self.existing
        different = SimpleUploadedFile("different.jpg", b"different raw source")
        with patch.object(uploads.transaction, "atomic", return_value=nullcontext()), self.assertRaises(ValidationError):
            uploads.create_asset(organization=self.organization, actor=self.actor,
                                 kind="image", file=different, public_id="same-identifier")

    @patch.object(uploads, "ensure_organization_content_writes_enabled")
    @patch.object(uploads, "ensure_content_manager")
    @patch.object(uploads, "_validate_upload", side_effect=ValidationError("Safety blocked"))
    @patch.object(OrganizationMediaAsset, "objects")
    def test_validation_failure_precedes_storage_and_transaction(self, asset_manager, validate, permission, enabled):
        asset_manager.filter.return_value.first.return_value = None
        with patch.object(uploads.transaction, "atomic") as atomic, self.assertRaises(ValidationError):
            uploads.create_asset(organization=self.organization, actor=self.actor,
                                 kind="image", file=self.file, public_id="new-identifier")
        atomic.assert_not_called()
