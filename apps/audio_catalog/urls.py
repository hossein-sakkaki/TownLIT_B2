# apps/audio_catalog/urls.py

from rest_framework.routers import DefaultRouter

from apps.audio_catalog.views import (
    AudioPlaybackAnalyticsViewSet,
    MusicTrackViewSet,
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

urlpatterns = router.urls