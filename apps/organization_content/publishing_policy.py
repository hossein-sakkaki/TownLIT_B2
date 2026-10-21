# apps/organization_content/publishing_policy.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-19.
# Last Update by Hossein Sakkaki on 2026-10-20.

from django.core.exceptions import ValidationError

from validators.mediaValidators.image_validators import (
    MOMENT_IMAGE_MAX_SIZE,
    MOMENT_MAX_IMAGES,
)
from validators.mediaValidators.ugc_policies import MOMENT_VIDEO_POLICY


# Use the current raw-photo and short-video policies without another validator.
MAX_PHOTOS = MOMENT_MAX_IMAGES
MAX_IMAGE_BYTES = MOMENT_IMAGE_MAX_SIZE
VIDEO_POLICY = MOMENT_VIDEO_POLICY
MAX_CAPTION_WORDS = 2500


def validate_media_selection(assets, *, require_media=False):
    kinds = [asset.kind for asset in assets]
    if not kinds:
        if require_media:
            raise ValidationError({
                "media_public_ids": "Add at least one photo or a video before publishing.",
            })
        return
    if all(kind == "image" for kind in kinds) and len(kinds) <= MAX_PHOTOS:
        return
    if kinds == ["video"]:
        return
    raise ValidationError({
        "media_public_ids": f"Choose up to {MAX_PHOTOS} photos or one video.",
    })


def upload_policy_payload():
    return {
        "max_caption_words": MAX_CAPTION_WORDS,
        "max_photos": MAX_PHOTOS,
        "max_image_mb": MAX_IMAGE_BYTES / (1024 * 1024),
        "video": {
            "min_duration_seconds": VIDEO_POLICY.min_duration_sec,
            "max_duration_seconds": VIDEO_POLICY.max_duration_sec,
            "min_fps": VIDEO_POLICY.min_fps,
            "max_fps": VIDEO_POLICY.max_fps,
            "cap_mb": VIDEO_POLICY.cap_mb,
            "mb_per_minute": VIDEO_POLICY.mb_per_minute,
        },
    }

