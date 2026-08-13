# apps/posts/services/journeys/music.py

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import ValidationError

from apps.audio_catalog.models import (
    MusicTrack,
    MusicTrackVariant,
)
from apps.audio_catalog.services.usage import (
    UsageSelection,
)
from apps.posts.constants.journeys import (
    JOURNEY_MAX_DURATION_MS,
    JOURNEY_MEDIA_DURATION_TOLERANCE_MS,
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
    required_duration_ms: int | None = None,
) -> JourneyMusicSelection:
    """
    Apply Journey-specific music rules.

    For video Journeys, required_duration_ms is the
    canonical rendered video duration. The selected music
    window must match that duration within the configured
    technical tolerance.

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

    start_ms = int(
        clip_start_ms
    )

    end_ms = int(
        clip_end_ms
    )

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
                    "Music clip end must be greater "
                    "than its start."
                ),
            }
        )

    duration_ms = (
        end_ms - start_ms
    )

    validate_journey_music_clip_duration(
        duration_ms
    )

    if required_duration_ms is not None:
        validate_journey_music_video_compatibility(
            music_duration_ms=duration_ms,
            video_duration_ms=
                required_duration_ms,
        )

    normalized_volume = Decimal(
        str(
            music_volume
        )
    )

    attribution_text = ""

    rights = getattr(
        track,
        "rights",
        None,
    )

    if (
        rights is not None
        and rights.attribution_required
    ):
        attribution_text = (
            rights.attribution_text
            or ""
        )

    usage_selection = UsageSelection(
        track=track,
        variant=variant,
        clip_start_ms=start_ms,
        clip_duration_ms=duration_ms,
        music_volume=float(
            normalized_volume
        ),

        # Music usage is tracked independently
        # from visual media source audio.
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


def validate_journey_music_clip_duration(
    duration_ms: int,
) -> None:
    duration = int(
        duration_ms
    )

    if duration < JOURNEY_MIN_DURATION_MS:
        raise ValidationError(
            {
                "music_clip_end_ms": (
                    "Journey music must be at least "
                    "15 seconds."
                ),
            }
        )

    if duration > JOURNEY_MAX_DURATION_MS:
        raise ValidationError(
            {
                "music_clip_end_ms": (
                    "Journey music cannot exceed "
                    "60 seconds."
                ),
            }
        )


def validate_journey_music_video_compatibility(
    *,
    music_duration_ms: int,
    video_duration_ms: int,
) -> None:
    music_duration = int(
        music_duration_ms
    )

    video_duration = int(
        video_duration_ms
    )

    if not (
        JOURNEY_MIN_DURATION_MS
        <= video_duration
        <= JOURNEY_MAX_DURATION_MS
    ):
        raise ValidationError(
            {
                "music": (
                    "Journey video duration is outside "
                    "the supported Journey range."
                ),
            }
        )

    difference_ms = abs(
        music_duration
        - video_duration
    )

    if (
        difference_ms
        <= JOURNEY_MEDIA_DURATION_TOLERANCE_MS
    ):
        return

    raise ValidationError(
        {
            "music": (
                "The selected music clip must match "
                "the Journey video duration."
            ),
            "music_clip_duration_ms": (
                music_duration
            ),
            "required_duration_ms": (
                video_duration
            ),
        }
    )