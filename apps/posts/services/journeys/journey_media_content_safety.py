#
#  apps/posts/services/journeys/journey_media_content_safety.py
#  TownLIT
#
#  Created by Hossein Sakkaki on 2026-08-14.
#  Last Update by Hossein Sakkaki on 2026-08-14.
#

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage

from apps.content_safety.enums import SafetyContext
from apps.content_safety.services.image import (
    enforce_image_file_safety,
)
from apps.content_safety.services.video import (
    enforce_video_file_safety,
)
from apps.posts.constants.journeys import (
    JourneyEntryMediaType,
)


# -------------------------------------------------
# Storage helpers
# -------------------------------------------------
def _normalize_storage_key(
    value,
) -> str:
    return str(
        value
        or ""
    ).strip().lstrip("/")


def _require_storage_asset(
    *,
    key: str,
    field_name: str,
) -> str:
    normalized = _normalize_storage_key(
        key
    )

    if not normalized:
        raise ValidationError(
            {
                field_name: (
                    "Journey render asset is unavailable."
                ),
            }
        )

    try:
        exists = default_storage.exists(
            normalized
        )
    except Exception as exc:
        raise ValidationError(
            {
                field_name: (
                    "Journey render asset could not be verified."
                ),
            }
        ) from exc

    if not exists:
        raise ValidationError(
            {
                field_name: (
                    "Journey render asset is unavailable."
                ),
            }
        )

    return normalized


# -------------------------------------------------
# Image safety
# -------------------------------------------------
def _enforce_rendered_image_safety(
    *,
    key: str,
    actor,
    field_name: str,
) -> None:
    normalized = _require_storage_asset(
        key=key,
        field_name=field_name,
    )

    try:
        with default_storage.open(
            normalized,
            "rb",
        ) as file_obj:
            enforce_image_file_safety(
                file_obj=file_obj,
                context=SafetyContext.JOURNEY_MEDIA,
                actor=actor,
                field_name=field_name,
                mime_type="image/jpeg",
            )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ValidationError(
            {
                field_name: (
                    "Journey image could not be inspected."
                ),
            }
        ) from exc


# -------------------------------------------------
# Video safety
# -------------------------------------------------
def _enforce_rendered_video_safety(
    *,
    key: str,
    actor,
    field_name: str,
) -> None:
    normalized = _require_storage_asset(
        key=key,
        field_name=field_name,
    )

    try:
        with default_storage.open(
            normalized,
            "rb",
        ) as file_obj:
            enforce_video_file_safety(
                file_obj=file_obj,
                context=SafetyContext.JOURNEY_MEDIA,
                actor=actor,
                field_name=field_name,
                mime_type="video/mp4",
            )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ValidationError(
            {
                field_name: (
                    "Journey video could not be inspected."
                ),
            }
        ) from exc


# -------------------------------------------------
# Final Journey render safety
# -------------------------------------------------
def enforce_journey_render_media_content_safety(
    *,
    media_type: str,
    rendered_key: str,
    thumbnail_key: str | None,
    actor,
) -> None:
    """
    Enforce Content Safety against the exact final Journey render.

    Important:
    - Image Journey:
        inspect the final rendered image.

    - Video Journey:
        inspect the generated poster first,
        then inspect the final rendered video.

    The final video inspection includes:
    - visual frame safety
    - audio extraction
    - transcription
    - transcript Text Safety using JOURNEY_TEXT context

    This deliberately runs after Creative Editor rendering but
    before JourneyEntry publication.

    Raw editor media is not authoritative because the user may:
    - crop it
    - resize it
    - rotate it
    - cover parts of it
    - combine multiple layers
    - mix video audio

    The final render is therefore the canonical publication input.
    """

    if media_type == JourneyEntryMediaType.IMAGE:
        _enforce_rendered_image_safety(
            key=rendered_key,
            actor=actor,
            field_name="rendered_image",
        )
        return

    if media_type == JourneyEntryMediaType.VIDEO:
        # The generated poster is publicly visible before playback.
        # Scan it independently as a cheap first visual gate.
        if thumbnail_key:
            _enforce_rendered_image_safety(
                key=thumbnail_key,
                actor=actor,
                field_name="thumbnail",
            )

        _enforce_rendered_video_safety(
            key=rendered_key,
            actor=actor,
            field_name="rendered_video",
        )
        return

    raise ValidationError(
        {
            "media_type": (
                "Unsupported Journey media type "
                "for Content Safety."
            ),
        }
    )