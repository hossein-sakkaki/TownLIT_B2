# apps/audio_catalog/tests/test_music_release_readiness.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-15.
# Last Update by Hossein Sakkaki on 2026-09-15.

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.audio_catalog.models import MusicRelease
from apps.audio_catalog.services.releases import (
    MusicReleaseReadiness,
    ReleaseReadinessCode,
    _publish_music_release_instance,
    evaluate_music_release_readiness,
)


class MusicReleaseReadinessTests(SimpleTestCase):
    databases = set()

    def setUp(self):
        self.track = SimpleNamespace(
            pk=11,
            id=11,
            catalog_id=1,
        )
        self.link = SimpleNamespace(
            track=self.track,
            track_id=11,
        )
        self.release = SimpleNamespace(
            status=MusicRelease.Status.DRAFT,
            release_type=MusicRelease.ReleaseType.SINGLE,
            release_date=date(2026, 9, 15),
            catalog=SimpleNamespace(is_active=True),
            catalog_id=1,
        )

    def evaluate(
        self,
        *,
        links=None,
        available=None,
        artwork=True,
        artist=True,
    ):
        links = [self.link] if links is None else links
        available = {11} if available is None else available

        with (
            patch(
                "apps.audio_catalog.services.releases._release_track_links",
                return_value=links,
            ),
            patch(
                "apps.audio_catalog.services.releases._available_track_ids",
                return_value=available,
            ),
            patch(
                "apps.audio_catalog.services.releases._has_primary_artwork",
                return_value=artwork,
            ),
            patch(
                "apps.audio_catalog.services.releases._has_primary_artist",
                return_value=artist,
            ),
        ):
            return evaluate_music_release_readiness(self.release)

    def test_ready_single(self):
        self.assertTrue(self.evaluate().ready)

    def test_release_requires_track(self):
        result = self.evaluate(links=[])

        self.assertIn(
            ReleaseReadinessCode.NO_TRACKS,
            result.blockers,
        )

    def test_single_requires_exactly_one_track(self):
        second = SimpleNamespace(
            track=SimpleNamespace(pk=12, catalog_id=1),
            track_id=12,
        )

        result = self.evaluate(
            links=[self.link, second],
            available={11, 12},
        )

        self.assertIn(
            ReleaseReadinessCode.SINGLE_TRACK_COUNT,
            result.blockers,
        )

    def test_all_tracks_must_be_available(self):
        result = self.evaluate(available=set())

        self.assertIn(
            ReleaseReadinessCode.TRACK_NOT_AVAILABLE,
            result.blockers,
        )

    def test_track_catalog_must_match_release(self):
        self.track.catalog_id = 2

        result = self.evaluate()

        self.assertIn(
            ReleaseReadinessCode.TRACK_CATALOG_MISMATCH,
            result.blockers,
        )

    def test_release_date_is_required(self):
        self.release.release_date = None

        result = self.evaluate()

        self.assertIn(
            ReleaseReadinessCode.MISSING_RELEASE_DATE,
            result.blockers,
        )

    def test_primary_artwork_is_required(self):
        result = self.evaluate(artwork=False)

        self.assertIn(
            ReleaseReadinessCode.MISSING_PRIMARY_ARTWORK,
            result.blockers,
        )

    def test_primary_artist_is_required(self):
        result = self.evaluate(artist=False)

        self.assertIn(
            ReleaseReadinessCode.MISSING_PRIMARY_ARTIST,
            result.blockers,
        )

    def test_catalog_must_be_active(self):
        self.release.catalog.is_active = False

        result = self.evaluate()

        self.assertIn(
            ReleaseReadinessCode.INACTIVE_CATALOG,
            result.blockers,
        )

    def test_suspended_release_cannot_publish(self):
        self.release.status = MusicRelease.Status.SUSPENDED

        result = self.evaluate()

        self.assertIn(
            ReleaseReadinessCode.INVALID_STATUS,
            result.blockers,
        )


class MusicReleasePublishTests(SimpleTestCase):
    databases = set()

    @patch(
        "apps.audio_catalog.services.releases.evaluate_music_release_readiness",
        return_value=MusicReleaseReadiness(()),
    )
    def test_publish_sets_canonical_state(self, readiness):
        release = MagicMock()
        release.status = MusicRelease.Status.DRAFT
        release.published_at = None
        release.suspended_at = None
        release.archived_at = None

        actor = SimpleNamespace(pk=7)

        result = _publish_music_release_instance(
            release,
            actor=actor,
        )

        self.assertIs(result, release)
        self.assertEqual(
            release.status,
            MusicRelease.Status.PUBLISHED,
        )
        self.assertIsNotNone(release.published_at)
        self.assertIs(release.updated_by, actor)

        release.clean.assert_called_once()
        release.save.assert_called_once()
        readiness.assert_called_once_with(release)

    @patch(
        "apps.audio_catalog.services.releases.evaluate_music_release_readiness",
        return_value=MusicReleaseReadiness(
            (ReleaseReadinessCode.NO_TRACKS,)
        ),
    )
    def test_publish_rejects_blocked_release(self, _readiness):
        release = MagicMock()
        release.status = MusicRelease.Status.DRAFT

        with self.assertRaises(ValidationError):
            _publish_music_release_instance(release)

        release.save.assert_not_called()