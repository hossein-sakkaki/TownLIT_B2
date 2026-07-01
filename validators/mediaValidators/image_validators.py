# validators/mediaValidators/image_validators.py

from io import BytesIO
import mimetypes

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

from validators.mime_type_validator import validate_file_type


# Keep the default/general image limit conservative.
# Used by avatars, thumbnails, posters, prayer images, etc.
IMAGE_MAX_SIZE = 5 * 1024 * 1024  # 5MB

# Moment photo uploads have their own raw-upload policy because
# a Moment can contain up to 7 photos and photos are converted later.
MOMENT_IMAGE_MAX_SIZE = 14 * 1024 * 1024  # 14MB per photo
MOMENT_MAX_IMAGES = 7
MOMENT_IMAGE_TOTAL_MAX_SIZE = MOMENT_IMAGE_MAX_SIZE * MOMENT_MAX_IMAGES


def _mb_text(size_bytes: int) -> str:
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def _file_size(value) -> int:
    size = getattr(value, "size", None)

    if size is None:
        raise ValidationError("TownLIT could not read this image file size.")

    return int(size)


def validate_image_size(image):
    if image.size > IMAGE_MAX_SIZE:
        raise ValidationError(
            f"The maximum image file size is {_mb_text(IMAGE_MAX_SIZE)}."
        )


def validate_moment_image_size(image):
    if image.size > MOMENT_IMAGE_MAX_SIZE:
        raise ValidationError(
            f"Each Moment photo can be up to {_mb_text(MOMENT_IMAGE_MAX_SIZE)}."
        )


def validate_moment_image_upload_batch(images):
    """
    Validate a raw Moment photo upload batch.

    Rules:
    - 1..7 photos
    - each photo <= 14MB
    - total size <= image_count * 14MB
      e.g. 7 photos => 98MB
    """
    images = list(images or [])
    count = len(images)

    if count < 1:
        raise ValidationError("Photo Moment requires at least one image.")

    if count > MOMENT_MAX_IMAGES:
        raise ValidationError(
            f"Photo Moment can contain up to {MOMENT_MAX_IMAGES} images."
        )

    total_size = 0

    for index, image in enumerate(images, start=1):
        validate_image_file(image)
        validate_moment_image_size(image)
        total_size += _file_size(image)

    max_total_size = count * MOMENT_IMAGE_MAX_SIZE

    if total_size > max_total_size:
        raise ValidationError(
            "Selected Moment photos are too large together. "
            f"Maximum total size for {count} photo(s) is {_mb_text(max_total_size)}; "
            f"selected total is {_mb_text(total_size)}."
        )


def validate_moment_image_items_metadata(image_items):
    """
    Validate JSON-backed Moment image_items size metadata.

    This is a defense-in-depth check for model.clean().
    The real upload serializer should still validate the uploaded files directly
    before storage using validate_moment_image_upload_batch(...).
    """
    if not isinstance(image_items, list):
        return

    items = [
        item for item in image_items
        if isinstance(item, dict) and item.get("key")
    ]

    if not items:
        return

    count = len(items)

    if count > MOMENT_MAX_IMAGES:
        raise ValidationError(
            f"Photo Moment can contain up to {MOMENT_MAX_IMAGES} images."
        )

    total_size = 0

    for item in items:
        raw_size = item.get("size") or 0

        try:
            size = int(raw_size)
        except (TypeError, ValueError):
            size = 0

        if size < 0:
            size = 0

        if size > MOMENT_IMAGE_MAX_SIZE:
            raise ValidationError(
                f"Each Moment photo can be up to {_mb_text(MOMENT_IMAGE_MAX_SIZE)}."
            )

        total_size += size

    max_total_size = count * MOMENT_IMAGE_MAX_SIZE

    if total_size > max_total_size:
        raise ValidationError(
            "Selected Moment photos are too large together. "
            f"Maximum total size for {count} photo(s) is {_mb_text(max_total_size)}; "
            f"selected total is {_mb_text(total_size)}."
        )


def validate_image_file(value):
    # Skip validation if value is not an uploaded file
    # e.g., default avatar path as string.
    if not hasattr(value, "file") or not hasattr(value, "read"):
        return

    mime_type, _ = mimetypes.guess_type(value.name)
    file_type = validate_file_type(value.name, mime_type)

    if file_type != "image":
        raise ValidationError("Only image files are allowed.")

    # HEIC validation is skipped because Pillow may not support it
    # consistently across environments. Size/type are still checked elsewhere.
    if value.name.lower().endswith(".heic"):
        return

    try:
        image_bytes = BytesIO(value.read())
        image = Image.open(image_bytes)
        image.verify()

    except (UnidentifiedImageError, OSError):
        raise ValidationError("This file is not a valid image.")
    except Exception as e:
        raise ValidationError(f"Image validation error: {str(e)}")
    finally:
        value.seek(0)