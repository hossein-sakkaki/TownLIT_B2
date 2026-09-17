# apps/audio_catalog/services/library.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-15.
# Last Update by Hossein Sakkaki on 2026-09-15.

from __future__ import annotations

from uuid import UUID

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.audio_catalog.models import (
    AudioUserTrackLibraryEntry,
    MusicTrack,
)
from apps.audio_catalog.querysets import published_tracks


def _get_available_track(track_public_id: UUID):
    try:
        return published_tracks().get(public_id=track_public_id)
    except MusicTrack.DoesNotExist as exc:
        raise NotFound("Track not found.") from exc


def _set_favorite(entry, is_favorite):
    if entry.is_favorite == is_favorite:
        return entry

    entry.is_favorite = is_favorite
    entry.favorited_at = timezone.now() if is_favorite else None
    entry.save(
        update_fields=(
            "is_favorite",
            "favorited_at",
            "updated_at",
        )
    )
    return entry


def _save_track(*, user, track_public_id: UUID):
    track = _get_available_track(track_public_id)

    entry, _ = AudioUserTrackLibraryEntry.objects.get_or_create(
        user=user,
        track=track,
    )
    return entry


@transaction.atomic
def save_track(*, user, track_public_id: UUID):
    return _save_track(
        user=user,
        track_public_id=track_public_id,
    )


def _set_track_favorite(
    *,
    user,
    track_public_id: UUID,
    is_favorite: bool,
):
    if is_favorite:
        entry = _save_track(
            user=user,
            track_public_id=track_public_id,
        )
    else:
        entry = (
            AudioUserTrackLibraryEntry.objects
            .filter(
                user=user,
                track__public_id=track_public_id,
            )
            .first()
        )

        if entry is None:
            return None

    return _set_favorite(entry, is_favorite)


@transaction.atomic
def set_track_favorite(
    *,
    user,
    track_public_id: UUID,
    is_favorite: bool,
):
    return _set_track_favorite(
        user=user,
        track_public_id=track_public_id,
        is_favorite=is_favorite,
    )


def _remove_track_from_library(*, user, track_public_id: UUID) -> bool:
    deleted, _ = AudioUserTrackLibraryEntry.objects.filter(
        user=user,
        track__public_id=track_public_id,
    ).delete()

    return deleted > 0


@transaction.atomic
def remove_track_from_library(*, user, track_public_id: UUID) -> bool:
    return _remove_track_from_library(
        user=user,
        track_public_id=track_public_id,
    )


def _set_track_library_state(
    *,
    user,
    track_public_id: UUID,
    is_saved: bool,
    is_favorite: bool,
):
    if not is_saved:
        _remove_track_from_library(
            user=user,
            track_public_id=track_public_id,
        )
        return None

    entry = _save_track(
        user=user,
        track_public_id=track_public_id,
    )
    return _set_favorite(entry, is_favorite)


@transaction.atomic
def set_track_library_state(
    *,
    user,
    track_public_id: UUID,
    is_saved: bool,
    is_favorite: bool,
):
    return _set_track_library_state(
        user=user,
        track_public_id=track_public_id,
        is_saved=is_saved,
        is_favorite=is_favorite,
    )


def library_state_for_track(*, user, track_public_id: UUID):
    return (
        AudioUserTrackLibraryEntry.objects
        .filter(
            user=user,
            track__public_id=track_public_id,
        )
        .first()
    )


def library_state_payload(entry) -> dict:
    if entry is None:
        return {
            "is_saved": False,
            "is_favorite": False,
            "saved_at": None,
            "favorited_at": None,
        }

    return {
        "is_saved": True,
        "is_favorite": entry.is_favorite,
        "saved_at": entry.created_at,
        "favorited_at": entry.favorited_at,
    }