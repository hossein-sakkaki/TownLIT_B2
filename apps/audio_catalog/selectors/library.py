# apps/audio_catalog/selectors/library.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-15.
# Last Update by Hossein Sakkaki on 2026-09-15.

from __future__ import annotations

from django.db.models import DateTimeField, F, OuterRef, Subquery

from apps.audio_catalog.models import AudioPlaybackSession
from apps.audio_catalog.querysets import published_tracks


def _library_tracks_for_user(user, *, favorites_only=False):
    filters = {"user_library_entries__user": user}

    if favorites_only:
        filters["user_library_entries__is_favorite"] = True

    return (
        published_tracks()
        .filter(**filters)
        .annotate(
            library_entry_id=F("user_library_entries__public_id"),
            library_is_favorite=F("user_library_entries__is_favorite"),
            library_saved_at=F("user_library_entries__created_at"),
            library_favorited_at=F("user_library_entries__favorited_at"),
        )
    )


def saved_library_tracks_for_user(user):
    return _library_tracks_for_user(user).order_by(
        "-library_saved_at",
        "-id",
    )


def favorite_library_tracks_for_user(user):
    return _library_tracks_for_user(
        user,
        favorites_only=True,
    ).order_by(
        "-library_favorited_at",
        "-library_saved_at",
        "-id",
    )


def recently_played_tracks_for_user(user):
    """
    One row per currently playable track ordered by the latest
    qualified playback session for this user.
    """

    latest_playback = (
        AudioPlaybackSession.objects
        .filter(
            user=user,
            track_id=OuterRef("pk"),
            is_test_session=False,
            qualified_play=True,
        )
        .order_by("-started_at", "-id")
        .values("started_at")[:1]
    )

    return (
        published_tracks()
        .annotate(
            user_last_played_at=Subquery(
                latest_playback,
                output_field=DateTimeField(),
            )
        )
        .filter(user_last_played_at__isnull=False)
        .order_by("-user_last_played_at", "-id")
    )