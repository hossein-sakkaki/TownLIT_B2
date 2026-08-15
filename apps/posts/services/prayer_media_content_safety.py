# apps/posts/services/prayer_media_content_safety.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-14.
# Last Update by Hossein Sakkaki on 2026-08-14.

from __future__ import annotations

from rest_framework import serializers

from apps.content_safety.enums import (
    SafetyContext,
)
from apps.content_safety.services.image import (
    enforce_image_file_safety,
)
from apps.content_safety.services.video import (
    enforce_video_file_safety,
)


# -----------------------------------------------------------------------------
# Internal image gate
# -----------------------------------------------------------------------------
def _enforce_image_asset(
    *,
    file_obj,
    actor,
    audit_field_name: str,
    validation_field_name: str,
) -> None:
    """
    Require one newly supplied Prayer image asset to pass Content Safety.

    Content Safety exceptions intentionally propagate unchanged so the
    API error handler can preserve the structured content_safety_* envelope.

    File-shape / media-format errors are exposed as normal DRF validation
    errors under the correct upload field.
    """

    if not file_obj:
        return

    try:
        enforce_image_file_safety(
            file_obj=file_obj,
            context=SafetyContext.PRAYER_MEDIA,
            actor=actor,
            field_name=audit_field_name,
            mime_type=getattr(
                file_obj,
                "content_type",
                None,
            ),
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise serializers.ValidationError(
            {
                validation_field_name: str(
                    exc
                )
            }
        ) from exc


# -----------------------------------------------------------------------------
# Internal video gate
# -----------------------------------------------------------------------------
def _enforce_video_asset(
    *,
    file_obj,
    actor,
    audit_field_name: str,
    validation_field_name: str,
) -> None:
    """
    Require one newly supplied Prayer video asset to pass Content Safety.
    """

    if not file_obj:
        return

    try:
        enforce_video_file_safety(
            file_obj=file_obj,
            context=SafetyContext.PRAYER_MEDIA,
            actor=actor,
            field_name=audit_field_name,
            mime_type=getattr(
                file_obj,
                "content_type",
                None,
            ),
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise serializers.ValidationError(
            {
                validation_field_name: str(
                    exc
                )
            }
        ) from exc


# -----------------------------------------------------------------------------
# Shared Prayer / PrayerResponse media gate
# -----------------------------------------------------------------------------
def _enforce_prayer_media_payload(
    *,
    validated_data,
    actor,
    audit_prefix: str,
) -> None:
    """
    Inspect only newly supplied media from one validated Prayer payload.

    Order is intentional:
    1. image
    2. thumbnail
    3. video

    Image checks are cheaper than full Video Safety. If one of the image
    assets is rejected, we avoid unnecessary frame extraction,
    transcription, and visual-video analysis.
    """

    image = validated_data.get(
        "image"
    )

    thumbnail = validated_data.get(
        "thumbnail"
    )

    video = validated_data.get(
        "video"
    )

    # -----------------------------------------------------------------
    # Required/main image
    # -----------------------------------------------------------------
    if image:
        _enforce_image_asset(
            file_obj=image,
            actor=actor,
            audit_field_name=(
                f"{audit_prefix}image"
            ),
            validation_field_name="image",
        )

    # -----------------------------------------------------------------
    # Optional thumbnail
    # -----------------------------------------------------------------
    if thumbnail:
        _enforce_image_asset(
            file_obj=thumbnail,
            actor=actor,
            audit_field_name=(
                f"{audit_prefix}thumbnail"
            ),
            validation_field_name="thumbnail",
        )

    # -----------------------------------------------------------------
    # Optional video
    # -----------------------------------------------------------------
    if video:
        _enforce_video_asset(
            file_obj=video,
            actor=actor,
            audit_field_name=(
                f"{audit_prefix}video"
            ),
            validation_field_name="video",
        )


# -----------------------------------------------------------------------------
# Public Prayer gate
# -----------------------------------------------------------------------------
def enforce_prayer_media_content_safety(
    *,
    validated_data,
    actor,
) -> None:
    """
    Require all newly supplied Prayer media to pass before persistence.

    CREATE:
    - required Prayer image
    - optional thumbnail
    - optional video

    UPDATE:
    - only media fields explicitly supplied in the update are inspected
    - existing unchanged media is not redundantly reprocessed
    """

    _enforce_prayer_media_payload(
        validated_data=validated_data,
        actor=actor,
        audit_prefix="",
    )


# -----------------------------------------------------------------------------
# Public PrayerResponse gate
# -----------------------------------------------------------------------------
def enforce_prayer_response_media_content_safety(
    *,
    validated_data,
    actor,
) -> None:
    """
    Require all newly supplied PrayerResponse media to pass before persistence.

    CREATE:
    - required response image
    - optional response thumbnail
    - optional response video

    UPDATE:
    - only newly supplied/replaced media is inspected
    """

    _enforce_prayer_media_payload(
        validated_data=validated_data,
        actor=actor,
        audit_prefix="response_",
    )