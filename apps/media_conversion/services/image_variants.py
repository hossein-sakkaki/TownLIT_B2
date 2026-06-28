# apps/media_conversion/services/image_variants.py

from __future__ import annotations

import os

from PIL import Image, ImageOps
from django.core.files.base import File
from django.core.files.storage import default_storage

from apps.media_conversion.services.media_metadata import (
    image_metadata_from_storage,
)


IMAGE_VARIANT_WIDTHS = {
    "thumb": 160,
    "grid": 480,
    "feed": 1080,
    "detail": 1600,
}


def build_image_variants(
    *,
    source_key: str,
    base_output_dir: str,
    basename: str,
    quality: int = 84,
) -> dict:
    """
    Build proportional JPEG variants from one ready image.
    """

    variants = {}
    source_key = str(source_key).lstrip("/")

    with default_storage.open(source_key, "rb") as source_file:
        with Image.open(source_file) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            source_width, source_height = image.size

            for name, target_width in IMAGE_VARIANT_WIDTHS.items():
                width = min(int(target_width), int(source_width))

                if width <= 0:
                    continue

                ratio = width / float(source_width)
                height = max(1, int(round(source_height * ratio)))

                resized = image.resize(
                    (width, height),
                    Image.Resampling.LANCZOS,
                )

                relative_path = (
                    f"{base_output_dir.rstrip('/')}/"
                    f"{basename}_{name}.jpg"
                )

                local_path = f"/tmp/{basename}_{name}_{os.getpid()}.jpg"

                try:
                    resized.save(
                        local_path,
                        "JPEG",
                        quality=quality,
                        optimize=True,
                        progressive=True,
                    )

                    with open(local_path, "rb") as file:
                        saved_key = default_storage.save(
                            relative_path,
                            File(file),
                        )

                    variants[name] = image_metadata_from_storage(saved_key)

                finally:
                    if os.path.exists(local_path):
                        os.remove(local_path)

    return variants