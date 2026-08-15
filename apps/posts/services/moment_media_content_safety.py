# apps/posts/services/moment_media_content_safety.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-14.
# Last Update by Hossein Sakkaki on 2026-08-14.

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
from apps.content_safety.services.video import (
    enforce_video_file_safety,
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
    intentionally supports both images and images[] conventions.
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
                    validation_field_name: (
                        str(
                            exc
                        )
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
    Require all new Moment photos to pass before persistence.

    Multi-photo Moments are inspected concurrently with a small bounded
    worker pool to keep upload latency low without creating excessive
    provider/database concurrency.
    """

    if not images:
        return

    if len(
        images
    ) == 1:
        _enforce_one_image(
            file_obj=images[
                0
            ],
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
            # Propagate Content Safety / validation failures.
            future.result()


def _enforce_thumbnail_upload(
    *,
    thumbnail,
    actor,
) -> None:
    """
    Inspect a user-supplied video thumbnail.

    Automatically generated thumbnails are not inspected here because
    their source video is already inspected by Video Safety.
    """

    if not thumbnail:
        return

    _enforce_one_image(
        file_obj=thumbnail,
        actor=actor,
        audit_field_name="thumbnail",
        validation_field_name="thumbnail",
    )


def _enforce_video_upload(
    *,
    video,
    actor,
) -> None:
    """
    Inspect one newly uploaded Moment video.
    """

    if not video:
        return

    try:
        enforce_video_file_safety(
            file_obj=video,
            context=SafetyContext.MOMENT_MEDIA,
            actor=actor,
            field_name="video",
            mime_type=getattr(
                video,
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
                "video": str(
                    exc
                )
            }
        ) from exc


def enforce_moment_media_content_safety(
    *,
    validated_data,
    request,
    actor,
) -> None:
    """
    Require all newly supplied Moment media to pass before persistence.

    CREATE:
    - legacy single image
    - multi-photo images / images[]
    - video
    - user-supplied video thumbnail

    UPDATE:
    - only newly supplied thumbnail requires inspection because Moment
      image/video replacement is prohibited by MomentSerializer.

    Existing stored media is intentionally not reprocessed on caption,
    visibility, or cover-selection updates.
    """

    images = _resolve_new_photo_uploads(
        validated_data=validated_data,
        request=request,
    )

    thumbnail = validated_data.get(
        "thumbnail"
    )

    video = validated_data.get(
        "video"
    )

    # Cheapest/newly supplied visual assets first.
    #
    # If an image/thumbnail fails, avoid unnecessary Video Safety work.
    _enforce_photo_uploads(
        images=images,
        actor=actor,
    )

    _enforce_thumbnail_upload(
        thumbnail=thumbnail,
        actor=actor,
    )

    _enforce_video_upload(
        video=video,
        actor=actor,
    )