# apps/audio_catalog/tests/test_music_library_api.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-15.
# Last Update by Hossein Sakkaki on 2026-09-15.

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.audio_catalog.views.library import MusicLibraryViewSet


class MusicLibraryAPITests(SimpleTestCase):
    databases = set()

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = SimpleNamespace(
            pk=101,
            is_authenticated=True,
        )
        self.track_id = uuid4()

    @patch(
        "apps.audio_catalog.views.library.saved_library_tracks_for_user",
        return_value=[],
    )
    def test_saved_list_is_paginated(self, selector):
        request = self.factory.get("/audio-catalog/library/")
        force_authenticate(request, user=self.user)

        response = MusicLibraryViewSet.as_view({"get": "list"})(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["results"], [])
        selector.assert_called_once_with(self.user)

    @patch(
        "apps.audio_catalog.views.library.favorite_library_tracks_for_user",
        return_value=[],
    )
    def test_favorites_list_is_paginated(self, selector):
        request = self.factory.get("/audio-catalog/library/favorites/")
        force_authenticate(request, user=self.user)

        response = MusicLibraryViewSet.as_view(
            {"get": "favorites"}
        )(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])
        selector.assert_called_once_with(self.user)

    @patch(
        "apps.audio_catalog.views.library.recently_played_tracks_for_user",
        return_value=[],
    )
    def test_recent_list_is_paginated(self, selector):
        request = self.factory.get("/audio-catalog/library/recent/")
        force_authenticate(request, user=self.user)

        response = MusicLibraryViewSet.as_view(
            {"get": "recent"}
        )(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])
        selector.assert_called_once_with(self.user)

    @patch("apps.audio_catalog.views.library.library_state_for_track")
    def test_track_state_get(self, state_for_track):
        now = datetime.now(timezone.utc)
        state_for_track.return_value = SimpleNamespace(
            is_favorite=True,
            created_at=now,
            favorited_at=now,
        )

        request = self.factory.get("/state/")
        force_authenticate(request, user=self.user)

        response = MusicLibraryViewSet.as_view(
            {"get": "track_state"}
        )(
            request,
            track_public_id=str(self.track_id),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_saved"])
        self.assertTrue(response.data["is_favorite"])

    @patch("apps.audio_catalog.views.library.set_track_library_state")
    def test_track_state_put(self, set_state):
        now = datetime.now(timezone.utc)
        set_state.return_value = SimpleNamespace(
            is_favorite=True,
            created_at=now,
            favorited_at=now,
        )

        request = self.factory.put(
            "/state/",
            {
                "is_saved": True,
                "is_favorite": True,
            },
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = MusicLibraryViewSet.as_view(
            {"put": "track_state"}
        )(
            request,
            track_public_id=str(self.track_id),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_favorite"])

        set_state.assert_called_once_with(
            user=self.user,
            track_public_id=self.track_id,
            is_saved=True,
            is_favorite=True,
        )

    @patch("apps.audio_catalog.views.library.set_track_library_state")
    def test_favorite_without_saved_is_rejected(self, set_state):
        request = self.factory.put(
            "/state/",
            {
                "is_saved": False,
                "is_favorite": True,
            },
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = MusicLibraryViewSet.as_view(
            {"put": "track_state"}
        )(
            request,
            track_public_id=str(self.track_id),
        )

        self.assertEqual(response.status_code, 400)
        set_state.assert_not_called()

    @patch("apps.audio_catalog.views.library.remove_track_from_library")
    def test_track_state_delete(self, remove_track):
        request = self.factory.delete("/state/")
        force_authenticate(request, user=self.user)

        response = MusicLibraryViewSet.as_view(
            {"delete": "track_state"}
        )(
            request,
            track_public_id=str(self.track_id),
        )

        self.assertEqual(response.status_code, 204)
        remove_track.assert_called_once_with(
            user=self.user,
            track_public_id=self.track_id,
        )

    def test_invalid_track_id_returns_404(self):
        request = self.factory.get("/state/")
        force_authenticate(request, user=self.user)

        response = MusicLibraryViewSet.as_view(
            {"get": "track_state"}
        )(
            request,
            track_public_id="not-a-uuid",
        )

        self.assertEqual(response.status_code, 404)