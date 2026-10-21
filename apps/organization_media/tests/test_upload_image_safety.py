# apps/organization_media/tests/test_upload_image_safety.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-19.
# Last Update by Hossein Sakkaki on 2026-10-19.

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from PIL import Image
from rest_framework import serializers

from apps.content_safety.enums import SafetyContext, SafetyDecision
from apps.content_safety.exceptions import (
    ContentSafetyBlockedError, ContentSafetyReviewError, ContentSafetyUnavailableError,
)
from apps.content_safety.services import image as image_safety
from apps.content_safety.services.media_types import ImageSafetyResult
from apps.core.exceptions import custom_exception_handler
from apps.organization_media.models import OrganizationMediaAsset
from apps.organization_media.services import uploads
from apps.organizations.views.helpers import raise_drf_validation_error


@override_settings(
    CONTENT_SAFETY_ENABLED=False,
    CONTENT_SAFETY_MAX_IMAGE_BYTES=20 * 1024 * 1024,
)
class UploadImageSafetyTests(SimpleTestCase):
    """Exercise real image parsing and safety input validation without providers.

    Only these tests disable provider evaluation. Format checks still run in
    the real shared safety core, before its feature flag is evaluated.
    """

    def setUp(self):
        self.actor = SimpleNamespace(pk=42)

    def image_file(self, image_format, *, name=None, content_type=None):
        data = BytesIO()
        Image.new("RGB", (2, 2), "white").save(data, format=image_format)
        extension = "jpg" if image_format == "JPEG" else image_format.lower()
        return SimpleUploadedFile(
            name or f"source.{extension}", data.getvalue(),
            content_type=content_type or f"image/{image_format.lower()}",
        )

    def validate(self, file, *, kind="image", thumbnail=None):
        return uploads._validate_upload(
            kind=kind, file=file, thumbnail=thumbnail,
            actor=self.actor, alt_text="", caption="",
        )

    def create_without_storage(self, file):
        with (
            patch.object(uploads, "ensure_organization_content_writes_enabled"),
            patch.object(uploads, "ensure_content_manager"),
            patch.object(OrganizationMediaAsset, "objects") as manager,
            patch.object(OrganizationMediaAsset, "save") as save,
            patch.object(uploads.transaction, "atomic") as atomic,
        ):
            manager.filter.return_value.first.return_value = None
            try:
                return uploads.create_asset(
                    organization=SimpleNamespace(pk=17), actor=self.actor,
                    kind="image", file=file,
                )
            finally:
                atomic.assert_not_called()
                save.assert_not_called()

    def test_noncanonical_image_is_a_field_error_before_storage(self):
        files = (
            self.image_file("TIFF"),
            self.image_file("GIF"),
            SimpleUploadedFile(
                "source.heic", b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00",
                content_type="image/heic",
            ),
        )
        for file in files:
            with self.subTest(name=file.name):
                with self.assertRaises(ValidationError) as raised:
                    self.create_without_storage(file)
                self.assertIn("file", raised.exception.message_dict)
                self.assertIsInstance(raised.exception.__cause__, ValueError)
                self.assertEqual(file.tell(), 0)

    def test_file_extension_and_mime_relabeling_cannot_bypass_format_check(self):
        file = self.image_file("PNG", name="renamed.jpg", content_type="image/jpeg")

        with self.assertRaises(ValidationError) as raised:
            self.validate(file)

        self.assertIn("file", raised.exception.message_dict)
        self.assertIn("does not match", raised.exception.message_dict["file"][0])
        self.assertEqual(file.tell(), 0)

    def test_supported_images_reach_the_shared_safety_service_with_original_bytes(self):
        for image_format in ("JPEG", "PNG", "WEBP"):
            with self.subTest(image_format=image_format):
                file = self.image_file(image_format)
                original = file.read()
                file.seek(0)
                with patch.object(
                    uploads, "enforce_image_file_safety",
                    wraps=image_safety.enforce_image_file_safety,
                ) as safety:
                    self.validate(file)
                safety.assert_called_once_with(
                    file_obj=file, context=SafetyContext.GENERIC, actor=self.actor,
                    field_name="file", mime_type=file.content_type,
                )
                self.assertEqual(file.tell(), 0)
                self.assertEqual(file.read(), original)

    def test_invalid_thumbnail_has_its_own_field_error(self):
        file = SimpleUploadedFile("source.mov", b"video source", content_type="video/quicktime")
        thumbnail = self.image_file("TIFF")

        with patch.object(uploads, "validate_video_file") as validate_video:
            with self.assertRaises(ValidationError) as raised:
                self.validate(file, kind="video", thumbnail=thumbnail)

        validate_video.assert_called_once_with(file, policy=uploads.VIDEO_POLICY)
        self.assertEqual(set(raised.exception.message_dict), {"thumbnail"})
        self.assertEqual(thumbnail.tell(), 0)

    @override_settings(CONTENT_SAFETY_ENABLED=True)
    def test_safety_block_and_review_still_prevent_storage(self):
        for decision, exception_type in (
            (SafetyDecision.BLOCK, ContentSafetyBlockedError),
            (SafetyDecision.REVIEW, ContentSafetyReviewError),
        ):
            with self.subTest(decision=decision):
                file = self.image_file("JPEG")
                result = ImageSafetyResult(
                    decision=decision, risk_level="high",
                    reason_code="provider_flagged", input_hash="test-source",
                )
                with patch.object(image_safety, "check_image_safety", return_value=result):
                    with self.assertRaises(exception_type) as raised:
                        self.create_without_storage(file)
                self.assertEqual(raised.exception.status_code, 422)
                self.assertEqual(file.tell(), 0)

    @override_settings(CONTENT_SAFETY_ENABLED=True)
    def test_safety_unavailability_still_prevents_storage(self):
        file = self.image_file("JPEG")
        failure = ContentSafetyUnavailableError()

        with patch.object(image_safety, "check_image_safety", side_effect=failure):
            with self.assertRaises(ContentSafetyUnavailableError) as raised:
                self.create_without_storage(file)

        self.assertIs(raised.exception, failure)
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(file.tell(), 0)

    def test_input_type_error_is_a_field_error_and_rewinds_the_file(self):
        file = self.image_file("JPEG")

        def invalid_input(**kwargs):
            kwargs["file_obj"].read()
            raise TypeError("image_bytes must be bytes-like.")

        with patch.object(uploads, "enforce_image_file_safety", side_effect=invalid_input):
            with self.assertRaises(ValidationError) as raised:
                self.validate(file)

        self.assertIn("file", raised.exception.message_dict)
        self.assertIsInstance(raised.exception.__cause__, TypeError)
        self.assertEqual(file.tell(), 0)

    def test_invalid_format_uses_the_existing_api_400_envelope(self):
        file = self.image_file("TIFF")

        with self.assertRaises(ValidationError) as raised:
            self.validate(file)
        with self.assertRaises(serializers.ValidationError) as api_error:
            raise_drf_validation_error(raised.exception)
        response = custom_exception_handler(api_error.exception, {})

        self.assertEqual(response.status_code, 400)
        self.assertIn("file", response.data["error"])
