# apps/organization_content/tests/test_asset_publication.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-19.
# Last Update by Hossein Sakkaki on 2026-10-19.

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase

from apps.media_conversion.models import MediaConversionJob
from apps.organization_media.models import OrganizationMediaAsset


class AssetPublicationTests(SimpleTestCase):
    def asset(self, **changes):
        content_type = ContentType(
            pk=73, app_label="organization_media", model="organizationmediaasset",
        )
        asset = SimpleNamespace(
            pk=4, Status=OrganizationMediaAsset.Status, Kind=OrganizationMediaAsset.Kind,
            status="ready", kind="image", is_converted=True, image_safety_verified=True,
            file=SimpleNamespace(name="organization_media/output.jpg"),
            media_conversion_target_ready_for_availability=lambda: True,
            _get_content_type=lambda: content_type,
            content_safety_jobs=MagicMock(),
        )
        asset.is_available = lambda: OrganizationMediaAsset.is_available(asset)
        for name, value in changes.items():
            setattr(asset, name, value)
        return asset

    def test_verified_converted_photo_is_ready(self):
        self.assertTrue(OrganizationMediaAsset.is_ready_for_publication(self.asset()))

    def test_legacy_ready_status_is_not_a_safety_proof(self):
        self.assertFalse(OrganizationMediaAsset.is_ready_for_publication(self.asset(is_converted=False)))
        self.assertFalse(OrganizationMediaAsset.is_ready_for_publication(self.asset(image_safety_verified=False)))

    def test_matching_conversion_is_required(self):
        asset = self.asset(media_conversion_target_ready_for_availability=lambda: False)
        self.assertFalse(OrganizationMediaAsset.is_ready_for_publication(asset))

    def test_processing_and_archived_assets_are_not_ready(self):
        for status in ("processing", "archived", "failed", "draft"):
            with self.subTest(status=status):
                self.assertFalse(OrganizationMediaAsset.is_ready_for_publication(self.asset(status=status)))

    @patch.object(MediaConversionJob, "objects")
    def test_video_requires_allow_for_the_converted_source(self, manager):
        asset = self.asset(kind="video", file=SimpleNamespace(name="output/master.m3u8"))
        source = SimpleNamespace(source_path="original/generation-1.mov")
        manager.filter.return_value.order_by.return_value.first.return_value = source
        # System checks can rebuild Django's cached manager instances.
        MediaConversionJob._meta._expire_cache()
        asset.content_safety_jobs.filter.return_value.exists.return_value = False
        self.assertFalse(OrganizationMediaAsset.is_ready_for_publication(asset))
        asset.content_safety_jobs.filter.return_value.exists.return_value = True
        self.assertTrue(OrganizationMediaAsset.is_ready_for_publication(asset))
        self.assertEqual(manager.filter.call_args.kwargs["output_path"], "output/master.m3u8")
        self.assertEqual(manager.filter.call_args.kwargs["content_type"], asset._get_content_type())
        self.assertEqual(asset.content_safety_jobs.filter.call_args.kwargs["source_path"], "original/generation-1.mov")
        self.assertEqual(asset.content_safety_jobs.filter.call_args.kwargs["decision"], "allow")

    @patch.object(MediaConversionJob, "objects")
    def test_video_without_matching_conversion_is_not_ready(self, manager):
        manager.filter.return_value.order_by.return_value.first.return_value = None
        self.assertFalse(OrganizationMediaAsset.is_ready_for_publication(self.asset(kind="video")))
