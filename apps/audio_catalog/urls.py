# apps/audio_catalog/urls.py

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.audio_catalog.views import (
    AudioPlaybackAnalyticsViewSet,
    MusicTrackLyricsView,
    MusicTrackViewSet,
    MusicLibraryViewSet,
    MusicReleaseViewSet,
)


app_name = "audio_catalog"

router = DefaultRouter()

router.register(
    "tracks",
    MusicTrackViewSet,
    basename="tracks",
)

router.register(
    "analytics/playback",
    AudioPlaybackAnalyticsViewSet,
    basename="playback-analytics",
)

router.register(
    "library",
    MusicLibraryViewSet,
    basename="music-library",
)

router.register(
    "releases",
    MusicReleaseViewSet,
    basename="music-releases",
)

urlpatterns = [
    path(
        "tracks/<uuid:public_id>/lyrics/",
        MusicTrackLyricsView.as_view(),
        name="track-lyrics",
    ),
    *router.urls,
]