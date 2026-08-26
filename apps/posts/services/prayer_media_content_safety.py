#
# apps/posts/services/prayer_media_content_safety.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-14.
# Last Update by Hossein Sakkaki on 2026-08-25.
#

from __future__ import annotations

from rest_framework import serializers

from apps.content_safety.enums import (
    SafetyContext,
)
from apps.content_safety.services.image import (
    enforce_image_file_safety,
)


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
    structured API safety contract remains intact.

    Media-format errors are exposed as ordinary DRF validation errors.
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


def _enforce_prayer_media_payload(
    *,
    validated_data,
    actor,
    audit_prefix: str,
) -> None:
    """
    Inspect only newly supplied inexpensive image assets.

    Image and thumbnail safety remains synchronous.

    Raw video safety is intentionally asynchronous:
    persistent source -> ContentSafetyJob -> ALLOW -> MediaConversionJob.
    """

    image = validated_data.get(
        "image"
    )

    thumbnail = validated_data.get(
        "thumbnail"
    )

    if image:
        _enforce_image_asset(
            file_obj=image,
            actor=actor,
            audit_field_name=(
                f"{audit_prefix}image"
            ),
            validation_field_name="image",
        )

    if thumbnail:
        _enforce_image_asset(
            file_obj=thumbnail,
            actor=actor,
            audit_field_name=(
                f"{audit_prefix}thumbnail"
            ),
            validation_field_name="thumbnail",
        )


def enforce_prayer_media_content_safety(
    *,
    validated_data,
    actor,
) -> None:
    """
    Synchronous image safety for newly supplied Prayer media.

    Video is handled by the generic asynchronous ContentSafetyJob pipeline.
    """

    _enforce_prayer_media_payload(
        validated_data=validated_data,
        actor=actor,
        audit_prefix="",
    )


def enforce_prayer_response_media_content_safety(
    *,
    validated_data,
    actor,
) -> None:
    """
    Synchronous image safety for newly supplied PrayerResponse media.

    Video is handled by the generic asynchronous ContentSafetyJob pipeline.
    """

    _enforce_prayer_media_payload(
        validated_data=validated_data,
        actor=actor,
        audit_prefix="response_",
    )