# apps/audio_catalog/tests/test_offline_availability.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-15.
# Last Update by Hossein Sakkaki on 2026-09-15.

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from django.utils import timezone

from apps.audio_catalog.models import MusicRightsRecord, MusicTrack
from apps.audio_catalog.services.availability import (
    can_offline_play_track,
    can_stream_track,
    can_use_track,
)


class AudioOfflineAvailabilityTests(SimpleTestCase):
    databases = set()

    def setUp(self):
        self.rights = SimpleNamespace(
            status=MusicRightsRecord.Status.CLEARED,
            effective_from=None,
            effective_until=None,
            streaming_allowed=True,
            ugc_use_allowed=False,
            synchronization_allowed=False,
            clipping_allowed=False,
            hosting_allowed=False,
            sublicensing_to_end_users_allowed=False,
            standalone_download_allowed=False,
            offline_playback_allowed=True,
            external_export_allowed=False,
            territory_mode=MusicRightsRecord.TerritoryMode.WORLDWIDE,
            territory_codes=[],
        )

        self.track = SimpleNamespace(
            status=MusicTrack.Status.PUBLISHED,
            published_at=timezone.now(),
            is_test_asset=False,
            is_explicit=False,
            catalog=SimpleNamespace(is_active=True),
            allow_streaming=True,
            allow_ugc=False,
            allow_offline_playback=True,
            allow_standalone_download=False,
            rights=self.rights,
        )

        self.variant = SimpleNamespace(
            is_offline_eligible=True,
            is_downloadable=False,
        )

    @patch(
        "apps.audio_catalog.services.availability.current_track_origin_availability"
    )
    def test_streaming_does_not_require_ugc_rights(self, origin):
        origin.return_value = SimpleNamespace(allowed=True, reason="")

        result = can_stream_track(self.track)

        self.assertTrue(result.allowed)

    @patch(
        "apps.audio_catalog.services.availability.current_track_origin_availability"
    )
    def test_ugc_use_remains_separate_from_streaming(self, origin):
        origin.return_value = SimpleNamespace(allowed=True, reason="")

        with (
            patch(
                "apps.audio_catalog.services.availability._has_primary_artwork",
                return_value=True,
            ),
            patch(
                "apps.audio_catalog.services.availability._default_playback_variant",
                return_value=self.variant,
            ),
        ):
            result = can_use_track(self.track)

        self.assertFalse(result.allowed)

    @patch(
        "apps.audio_catalog.services.availability.current_track_origin_availability"
    )
    def test_offline_does_not_require_standalone_download(self, origin):
        origin.return_value = SimpleNamespace(allowed=True, reason="")

        result = can_offline_play_track(
            self.track,
            variant=self.variant,
        )

        self.assertTrue(result.allowed)

    @patch(
        "apps.audio_catalog.services.availability.current_track_origin_availability"
    )
    def test_offline_requires_track_policy(self, origin):
        origin.return_value = SimpleNamespace(allowed=True, reason="")
        self.track.allow_offline_playback = False

        result = can_offline_play_track(
            self.track,
            variant=self.variant,
        )

        self.assertFalse(result.allowed)

    @patch(
        "apps.audio_catalog.services.availability.current_track_origin_availability"
    )
    def test_offline_requires_rights_permission(self, origin):
        origin.return_value = SimpleNamespace(allowed=True, reason="")
        self.rights.offline_playback_allowed = False

        result = can_offline_play_track(
            self.track,
            variant=self.variant,
        )

        self.assertFalse(result.allowed)

    @patch(
        "apps.audio_catalog.services.availability.current_track_origin_availability"
    )
    def test_offline_requires_eligible_variant(self, origin):
        origin.return_value = SimpleNamespace(allowed=True, reason="")
        self.variant.is_offline_eligible = False

        result = can_offline_play_track(
            self.track,
            variant=self.variant,
        )

        self.assertFalse(result.allowed)

    @patch(
        "apps.audio_catalog.services.availability.current_track_origin_availability"
    )
    def test_revoked_rights_block_offline(self, origin):
        origin.return_value = SimpleNamespace(allowed=True, reason="")
        self.rights.status = MusicRightsRecord.Status.REVOKED

        result = can_offline_play_track(
            self.track,
            variant=self.variant,
        )

        self.assertFalse(result.allowed)