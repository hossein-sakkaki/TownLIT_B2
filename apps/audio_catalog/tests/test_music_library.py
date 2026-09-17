# apps/audio_catalog/tests/test_music_library.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-15.
# Last Update by Hossein Sakkaki on 2026-09-15.

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.test import SimpleTestCase
from rest_framework.exceptions import NotFound

from apps.audio_catalog.models import MusicTrack
from apps.audio_catalog.services.library import (
    _remove_track_from_library,
    _save_track,
    _set_track_favorite,
    library_state_for_track,
)


class AudioMusicLibraryServiceTests(SimpleTestCase):
    databases = set()

    def setUp(self):
        self.user = SimpleNamespace(pk=101)
        self.track_public_id = uuid4()
        self.track = SimpleNamespace(
            pk=202,
            public_id=self.track_public_id,
        )

    @patch("apps.audio_catalog.services.library.AudioUserTrackLibraryEntry.objects")
    @patch("apps.audio_catalog.services.library.published_tracks")
    def test_save_track_creates_or_returns_entry(
        self,
        published_tracks,
        library_objects,
    ):
        published_tracks.return_value.get.return_value = self.track
        entry = SimpleNamespace(
            user=self.user,
            track=self.track,
            is_favorite=False,
        )
        library_objects.get_or_create.return_value = (entry, True)

        result = _save_track(
            user=self.user,
            track_public_id=self.track_public_id,
        )

        published_tracks.return_value.get.assert_called_once_with(
            public_id=self.track_public_id
        )
        library_objects.get_or_create.assert_called_once_with(
            user=self.user,
            track=self.track,
        )
        self.assertIs(result, entry)

    @patch("apps.audio_catalog.services.library.published_tracks")
    def test_save_track_rejects_unavailable_track(self, published_tracks):
        published_tracks.return_value.get.side_effect = MusicTrack.DoesNotExist

        with self.assertRaises(NotFound):
            _save_track(
                user=self.user,
                track_public_id=self.track_public_id,
            )

    @patch("apps.audio_catalog.services.library.AudioUserTrackLibraryEntry.objects")
    @patch("apps.audio_catalog.services.library.published_tracks")
    def test_favorite_creates_saved_entry_and_sets_timestamp(
        self,
        published_tracks,
        library_objects,
    ):
        published_tracks.return_value.get.return_value = self.track

        entry = MagicMock()
        entry.is_favorite = False
        entry.favorited_at = None
        library_objects.get_or_create.return_value = (entry, True)

        result = _set_track_favorite(
            user=self.user,
            track_public_id=self.track_public_id,
            is_favorite=True,
        )

        self.assertIs(result, entry)
        self.assertTrue(entry.is_favorite)
        self.assertIsNotNone(entry.favorited_at)
        entry.save.assert_called_once_with(
            update_fields=(
                "is_favorite",
                "favorited_at",
                "updated_at",
            )
        )

    @patch("apps.audio_catalog.services.library.AudioUserTrackLibraryEntry.objects")
    @patch("apps.audio_catalog.services.library.published_tracks")
    def test_unfavorite_keeps_saved_entry(
        self,
        published_tracks,
        library_objects,
    ):
        published_tracks.return_value.get.return_value = self.track

        entry = MagicMock()
        entry.is_favorite = True
        entry.favorited_at = object()

        library_objects.filter.return_value.first.return_value = entry

        result = _set_track_favorite(
            user=self.user,
            track_public_id=self.track_public_id,
            is_favorite=False,
        )

        self.assertIs(result, entry)
        self.assertFalse(entry.is_favorite)
        self.assertIsNone(entry.favorited_at)

        library_objects.filter.assert_called_once_with(
            user=self.user,
            track__public_id=self.track_public_id,
        )

        entry.save.assert_called_once_with(
            update_fields=(
                "is_favorite",
                "favorited_at",
                "updated_at",
            )
        )

    @patch("apps.audio_catalog.services.library.AudioUserTrackLibraryEntry.objects")
    @patch("apps.audio_catalog.services.library.published_tracks")
    def test_unfavorite_does_not_create_missing_library_entry(
        self,
        published_tracks,
        library_objects,
    ):
        published_tracks.return_value.get.return_value = self.track
        library_objects.filter.return_value.first.return_value = None

        result = _set_track_favorite(
            user=self.user,
            track_public_id=self.track_public_id,
            is_favorite=False,
        )

        self.assertIsNone(result)
        library_objects.get_or_create.assert_not_called()
        
    @patch("apps.audio_catalog.services.library.AudioUserTrackLibraryEntry.objects")
    @patch("apps.audio_catalog.services.library.published_tracks")
    def test_unchanged_favorite_state_does_not_write(
        self,
        published_tracks,
        library_objects,
    ):
        published_tracks.return_value.get.return_value = self.track

        entry = MagicMock()
        entry.is_favorite = True
        library_objects.get_or_create.return_value = (entry, False)

        result = _set_track_favorite(
            user=self.user,
            track_public_id=self.track_public_id,
            is_favorite=True,
        )

        self.assertIs(result, entry)
        entry.save.assert_not_called()

    @patch("apps.audio_catalog.services.library.AudioUserTrackLibraryEntry.objects")
    def test_remove_track_returns_true_when_deleted(self, library_objects):
        queryset = library_objects.filter.return_value
        queryset.delete.return_value = (1, {})

        result = _remove_track_from_library(
            user=self.user,
            track_public_id=self.track_public_id,
        )

        library_objects.filter.assert_called_once_with(
            user=self.user,
            track__public_id=self.track_public_id,
        )
        self.assertTrue(result)

    @patch("apps.audio_catalog.services.library.AudioUserTrackLibraryEntry.objects")
    def test_remove_track_returns_false_when_missing(self, library_objects):
        library_objects.filter.return_value.delete.return_value = (0, {})

        result = _remove_track_from_library(
            user=self.user,
            track_public_id=self.track_public_id,
        )

        self.assertFalse(result)

    @patch("apps.audio_catalog.services.library.AudioUserTrackLibraryEntry.objects")
    def test_library_state_returns_existing_entry(self, library_objects):
        entry = SimpleNamespace(is_favorite=True)
        library_objects.filter.return_value.first.return_value = entry

        result = library_state_for_track(
            user=self.user,
            track_public_id=self.track_public_id,
        )

        library_objects.filter.assert_called_once_with(
            user=self.user,
            track__public_id=self.track_public_id,
        )
        self.assertIs(result, entry)

    @patch("apps.audio_catalog.services.library.AudioUserTrackLibraryEntry.objects")
    def test_library_state_returns_none_when_not_saved(self, library_objects):
        library_objects.filter.return_value.first.return_value = None

        result = library_state_for_track(
            user=self.user,
            track_public_id=self.track_public_id,
        )

        self.assertIsNone(result)