# apps/organization_content/tests/test_media_required.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-20.
# Last Update by Hossein Sakkaki on 2026-10-20.

from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.organization_content.publishing_policy import validate_media_selection


class OrganizationMediaRequiredPolicyTests(SimpleTestCase):
    def test_unfinished_draft_may_have_no_media(self):
        validate_media_selection([])

    def test_publication_requires_a_photo_or_video(self):
        with self.assertRaises(ValidationError) as raised:
            validate_media_selection([], require_media=True)
        self.assertIn("media_public_ids", raised.exception.message_dict)

    def test_single_photo_is_allowed(self):
        validate_media_selection([SimpleNamespace(kind="image")], require_media=True)

    def test_single_video_is_allowed(self):
        validate_media_selection([SimpleNamespace(kind="video")], require_media=True)

    def test_mixed_photo_and_video_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_media_selection(
                [SimpleNamespace(kind="image"), SimpleNamespace(kind="video")],
                require_media=True,
            )
