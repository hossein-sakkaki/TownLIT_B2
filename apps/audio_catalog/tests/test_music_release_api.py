# apps/audio_catalog/tests/test_music_release_api.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-15.
# Last Update by Hossein Sakkaki on 2026-09-15.

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.audio_catalog.views.releases import MusicReleaseViewSet


class MusicReleaseAPITests(SimpleTestCase):
    databases = set()

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = SimpleNamespace(
            pk=101,
            is_authenticated=True,
        )

    @patch(
        "apps.audio_catalog.views.releases.published_releases",
        return_value=[],
    )
    def test_release_list_is_paginated(self, selector):
        request = self.factory.get("/audio-catalog/releases/")
        force_authenticate(request, user=self.user)

        response = MusicReleaseViewSet.as_view(
            {"get": "list"}
        )(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["results"], [])
        selector.assert_called_once()

    def test_list_and_detail_use_separate_serializers(self):
        view = MusicReleaseViewSet()

        view.action = "list"
        self.assertEqual(
            view.get_serializer_class().__name__,
            "ReleaseListSerializer",
        )

        view.action = "retrieve"
        self.assertEqual(
            view.get_serializer_class().__name__,
            "ReleaseDetailSerializer",
        )