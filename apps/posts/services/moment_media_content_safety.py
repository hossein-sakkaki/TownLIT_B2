#
# apps/posts/services/moment_media_content_safety.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-14.
# Last Update by Hossein Sakkaki on 2026-08-25.
#

from __future__ import annotations

from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)

from django.db import close_old_connections

from rest_framework import serializers

from apps.content_safety.enums import (
    SafetyContext,
)
from apps.content_safety.services.image import (
    enforce_image_file_safety,
)


_MAX_PARALLEL_IMAGE_CHECKS = 4


def _request_multi_images(
    *,
    request,
) -> list:
    """
    Resolve Moment multi-photo files directly from multipart input.

    Supports both:
    - images
    - images[]
    """

    files = getattr(
        request,
        "FILES",
        None,
    )

    if not files or not hasattr(
        files,
        "getlist",
    ):
        return []

    images = files.getlist(
        "images"
    )

    if images:
        return list(
            images
        )

    images = files.getlist(
        "images[]"
    )

    if images:
        return list(
            images
        )

    return []


def _validated_multi_images(
    *,
    validated_data,
) -> list:
    """
    Resolve validated multi-photo files when available.
    """

    raw = validated_data.get(
        "images"
    )

    if not raw:
        return []

    if isinstance(
        raw,
        (
            list,
            tuple,
        ),
    ):
        return [
            value
            for value in raw
            if value is not None
        ]

    return [
        raw
    ]


def _resolve_new_photo_uploads(
    *,
    validated_data,
    request,
) -> list:
    """
    Return only newly supplied Moment photo files.

    Multipart request files are preferred because MomentSerializer
    supports both images and images[] conventions.
    """

    multipart_images = _request_multi_images(
        request=request
    )

    if multipart_images:
        return multipart_images

    validated_images = _validated_multi_images(
        validated_data=validated_data
    )

    if validated_images:
        return validated_images

    legacy_image = validated_data.get(
        "image"
    )

    if legacy_image:
        return [
            legacy_image
        ]

    return []


def _enforce_one_image(
    *,
    file_obj,
    actor,
    audit_field_name: str,
    validation_field_name: str,
):
    """
    Inspect one newly uploaded Moment image.

    Content Safety exceptions intentionally propagate unchanged.
    Invalid media-shape errors are converted to normal serializer errors.
    """

    close_old_connections()

    try:
        try:
            return enforce_image_file_safety(
                file_obj=file_obj,
                context=SafetyContext.MOMENT_MEDIA,
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

    finally:
        close_old_connections()


def _enforce_photo_uploads(
    *,
    images: list,
    actor,
) -> None:
    """
    Require all newly supplied Moment photos to pass before persistence.

    Multi-photo Moments are inspected concurrently with a small bounded
    worker pool.
    """

    if not images:
        return

    if len(
        images
    ) == 1:
        _enforce_one_image(
            file_obj=images[0],
            actor=actor,
            audit_field_name="image",
            validation_field_name="image",
        )

        return

    max_workers = min(
        _MAX_PARALLEL_IMAGE_CHECKS,
        len(
            images
        ),
    )

    futures = []

    with ThreadPoolExecutor(
        max_workers=max_workers
    ) as executor:
        for index, image in enumerate(
            images
        ):
            futures.append(
                executor.submit(
                    _enforce_one_image,
                    file_obj=image,
                    actor=actor,
                    audit_field_name=(
                        f"images[{index}]"
                    ),
                    validation_field_name="images",
                )
            )

        for future in as_completed(
            futures
        ):
            future.result()


def _enforce_thumbnail_upload(
    *,
    thumbnail,
    actor,
) -> None:
    """
    Inspect a newly supplied Moment video thumbnail.

    The raw video itself is intentionally not inspected here.
    Video Safety is asynchronous and begins after persistence through
    the shared ContentSafetyJob pipeline.
    """

    if not thumbnail:
        return

    _enforce_one_image(
        file_obj=thumbnail,
        actor=actor,
        audit_field_name="thumbnail",
        validation_field_name="thumbnail",
    )


def enforce_moment_media_content_safety(
    *,
    validated_data,
    request,
    actor,
) -> None:
    """
    Run synchronous Content Safety only for inexpensive Moment image assets.

    CREATE:
    - legacy single image
    - multi-photo images / images[]
    - user-supplied video thumbnail

    VIDEO:
    - raw video is intentionally NOT inspected here
    - it is persisted first
    - a generic ContentSafetyJob is then scheduled
    - Media Conversion remains blocked for that exact source until ALLOW

    UPDATE:
    - only newly supplied thumbnail requires inspection because
      Moment image/video replacement is prohibited.
    """

    images = _resolve_new_photo_uploads(
        validated_data=validated_data,
        request=request,
    )

    thumbnail = validated_data.get(
        "thumbnail"
    )

    _enforce_photo_uploads(
        images=images,
        actor=actor,
    )

    _enforce_thumbnail_upload(
        thumbnail=thumbnail,
        actor=actor,
    )