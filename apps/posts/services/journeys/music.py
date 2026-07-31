# apps/posts/services/journeys/music.py

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import ValidationError

from apps.audio_catalog.models import MusicTrack, MusicTrackVariant
from apps.audio_catalog.services.usage import UsageSelection
from apps.posts.constants.journeys import (
    JOURNEY_MAX_DURATION_MS,
    JOURNEY_MIN_DURATION_MS,
)


@dataclass(frozen=True)
class JourneyMusicSelection:
    """
    Prepared Journey music selection.
    """

    track: MusicTrack
    variant: MusicTrackVariant

    clip_start_ms: int
    clip_end_ms: int
    clip_duration_ms: int

    music_volume: Decimal
    attribution_text: str

    usage_selection: UsageSelection


def prepare_journey_music_selection(
    *,
    track: MusicTrack,
    variant: MusicTrackVariant,
    clip_start_ms: int,
    clip_end_ms: int,
    music_volume,
) -> JourneyMusicSelection:
    """
    Apply Journey-specific music rules.

    Audio Catalog remains authoritative for:
    - track availability
    - catalog availability
    - rights and territory
    - track clip limits
    - variant readiness
    - source duration
    - volume configuration
    - usage grant creation
    """

    start_ms = int(clip_start_ms)
    end_ms = int(clip_end_ms)

    if start_ms < 0:
        raise ValidationError(
            {
                "music_clip_start_ms": (
                    "Music clip start cannot be negative."
                ),
            }
        )

    if end_ms <= start_ms:
        raise ValidationError(
            {
                "music_clip_end_ms": (
                    "Music clip end must be greater than its start."
                ),
            }
        )

    duration_ms = end_ms - start_ms

    if duration_ms < JOURNEY_MIN_DURATION_MS:
        raise ValidationError(
            {
                "music_clip_end_ms": (
                    "Journey music must be at least 15 seconds."
                ),
            }
        )

    if duration_ms > JOURNEY_MAX_DURATION_MS:
        raise ValidationError(
            {
                "music_clip_end_ms": (
                    "Journey music cannot exceed 60 seconds."
                ),
            }
        )

    normalized_volume = Decimal(str(music_volume))
    attribution_text = ""

    rights = getattr(track, "rights", None)

    if rights is not None and rights.attribution_required:
        attribution_text = rights.attribution_text or ""

    usage_selection = UsageSelection(
        track=track,
        variant=variant,
        clip_start_ms=start_ms,
        clip_duration_ms=duration_ms,
        music_volume=float(normalized_volume),

        # Journey v1 has no source audio.
        source_audio_volume=0.0,

        fade_in_ms=0,
        fade_out_ms=0,
    )

    return JourneyMusicSelection(
        track=track,
        variant=variant,
        clip_start_ms=start_ms,
        clip_end_ms=end_ms,
        clip_duration_ms=duration_ms,
        music_volume=normalized_volume,
        attribution_text=attribution_text,
        usage_selection=usage_selection,
    )