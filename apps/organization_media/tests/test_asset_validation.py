# apps/organization_media/tests/test_asset_validation.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-27.
# Last Update by Hossein Sakkaki on 2026-09-27.

from django.test import SimpleTestCase
from django.core.exceptions import ValidationError
from apps.organization_media.models import OrganizationMediaAsset


class MediaAssetTests(SimpleTestCase):
    def test_ready_asset_without_file_is_invalid(self):
        asset = OrganizationMediaAsset(pk=1, organization_id=1,
                                        kind="video", status="ready")
        with self.assertRaises(ValidationError):
            asset.clean()
