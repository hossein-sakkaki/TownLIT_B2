# apps/audio_catalog/models/library.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-15.
# Last Update by Hossein Sakkaki on 2026-09-15.

from __future__ import annotations

from django.conf import settings
from django.db import models

from .base import PublicIDTimestampedModel


class AudioUserTrackLibraryEntry(PublicIDTimestampedModel):
    """
    Explicit user-owned library state for one music track.

    Entry existence means the track is saved.
    Favorite is a stronger state inside the saved library.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="audio_library_entries",
    )

    track = models.ForeignKey(
        "audio_catalog.MusicTrack",
        on_delete=models.CASCADE,
        related_name="user_library_entries",
    )

    is_favorite = models.BooleanField(
        default=False,
        db_index=True,
    )

    favorited_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )

    class Meta:
        verbose_name = "Audio User Track Library Entry"
        verbose_name_plural = "Audio User Track Library Entries"

        constraints = [
            models.UniqueConstraint(
                fields=("user", "track"),
                name="audio_unique_user_track_library_entry",
            ),
        ]

        indexes = [
            models.Index(
                fields=("user", "-created_at"),
                name="audio_library_user_saved_idx",
            ),
            models.Index(
                fields=("user", "is_favorite", "-favorited_at"),
                name="audio_library_user_fav_idx",
            ),
        ]

        ordering = ("-created_at", "-id")

    def __str__(self) -> str:
        return f"{self.user_id} · {self.track_id}"