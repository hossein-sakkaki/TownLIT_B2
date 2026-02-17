# apps/subtitles/urls.py

from __future__ import annotations

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.subtitles.views import (
    SubtitleTrackViewSet,
    VoiceTrackViewSet,
)

router = DefaultRouter()
router.register(r"tracks", SubtitleTrackViewSet, basename="subtitle-track")
router.register(r"voices", VoiceTrackViewSet, basename="voice-track")

urlpatterns = [
    path("", include(router.urls)),
]
