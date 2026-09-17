# apps/audio_catalog/tests/test_music_releases.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-15.
# Last Update by Hossein Sakkaki on 2026-09-15.

from datetime import date

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from django.utils import timezone

from apps.audio_catalog.models import (
    AudioCatalog,
    MusicRelease,
    MusicReleaseArtwork,
    MusicReleaseTrack,
    MusicTrack,
)


class MusicReleaseDomainTests(SimpleTestCase):
    databases = set()

    def test_release_types_are_stable(self):
        self.assertEqual(
            set(MusicRelease.ReleaseType.values),
            {"single", "ep", "album"},
        )

    def test_slug_source_uses_title_and_subtitle(self):
        release = MusicRelease(
            title=" Grace ",
            subtitle=" Live ",
            release_type=MusicRelease.ReleaseType.EP,
        )

        self.assertEqual(release.get_slug_source(), "Grace Live")

    def test_published_release_requires_timestamp(self):
        release = MusicRelease(
            title="Grace",
            release_type=MusicRelease.ReleaseType.SINGLE,
            status=MusicRelease.Status.PUBLISHED,
        )

        with self.assertRaises(ValidationError):
            release.clean()

    def test_published_release_accepts_publish_timestamp(self):
        release = MusicRelease(
            title="Grace",
            release_type=MusicRelease.ReleaseType.SINGLE,
            status=MusicRelease.Status.PUBLISHED,
            published_at=timezone.now(),
            release_date=date(2026, 9, 15),
        )

        release.clean()

    def test_release_track_requires_same_catalog(self):
        first_catalog = AudioCatalog(pk=1, name="First")
        second_catalog = AudioCatalog(pk=2, name="Second")

        release = MusicRelease(
            pk=10,
            catalog=first_catalog,
            title="Grace",
            release_type=MusicRelease.ReleaseType.ALBUM,
        )
        track = MusicTrack(
            pk=20,
            catalog=second_catalog,
            title="Track",
        )

        link = MusicReleaseTrack(
            release=release,
            track=track,
            disc_number=1,
            track_number=1,
        )

        with self.assertRaises(ValidationError):
            link.clean()

    def test_release_track_accepts_same_catalog(self):
        catalog = AudioCatalog(pk=1, name="TownLIT Originals")

        release = MusicRelease(
            pk=10,
            catalog=catalog,
            title="Grace",
            release_type=MusicRelease.ReleaseType.ALBUM,
        )
        track = MusicTrack(
            pk=20,
            catalog=catalog,
            title="Track",
        )

        link = MusicReleaseTrack(
            release=release,
            track=track,
            disc_number=1,
            track_number=1,
        )

        link.clean()

    def test_release_track_rejects_zero_position(self):
        catalog = AudioCatalog(pk=1, name="TownLIT Originals")

        release = MusicRelease(
            pk=10,
            catalog=catalog,
            title="Grace",
            release_type=MusicRelease.ReleaseType.ALBUM,
        )
        track = MusicTrack(
            pk=20,
            catalog=catalog,
            title="Track",
        )

        link = MusicReleaseTrack(
            release=release,
            track=track,
            disc_number=1,
            track_number=0,
        )

        with self.assertRaises(ValidationError):
            link.clean()

    def test_release_artwork_primary_slot_tracks_active_state(self):
        release = MusicRelease(
            pk=10,
            title="Grace",
            release_type=MusicRelease.ReleaseType.SINGLE,
        )

        artwork = MusicReleaseArtwork(
            release=release,
            is_primary=True,
            is_active=True,
        )

        changed = artwork._sync_primary_slot()

        self.assertTrue(changed)
        self.assertEqual(artwork.primary_slot, 1)

        artwork.is_active = False
        artwork._sync_primary_slot()

        self.assertIsNone(artwork.primary_slot)