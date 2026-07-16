# utils/common/image_utils.py

import os
import logging

from PIL import Image, ImageFile, ImageOps
import pillow_heif

from django.conf import settings
from django.core.files.base import File
from django.core.files.storage import default_storage
from tempfile import NamedTemporaryFile

from utils.common.utils import FileUpload, get_converted_path

pillow_heif.register_heif_opener()
ImageFile.LOAD_TRUNCATED_IMAGES = True

logger = logging.getLogger(__name__)


def _normalized_rgb_image(image: Image.Image) -> Image.Image:
    """
    Return an RGB image ready for high-quality JPEG output.

    Notes:
    - Applies transparency over white for PNG/WebP/HEIC with alpha.
    - Avoids black backgrounds when converting transparent images to JPEG.
    - Keeps normal RGB images untouched when possible.
    """
    if image.mode in ("RGBA", "LA"):
        background = Image.new(
            "RGB",
            image.size,
            (255, 255, 255),
        )

        alpha = image.getchannel("A") if image.mode == "RGBA" else image.getchannel("A")
        rgb = image.convert("RGB")

        background.paste(
            rgb,
            mask=alpha,
        )

        return background

    if image.mode == "P":
        converted = image.convert("RGBA")

        if "A" in converted.getbands():
            return _normalized_rgb_image(converted)

        return converted.convert("RGB")

    if image.mode != "RGB":
        return image.convert("RGB")

    return image


def convert_image_to_jpg(
    source_path: str,
    instance,
    fileupload: FileUpload,
) -> str:
    """
    Convert uploaded image to normalized high-quality JPEG.

    Important:
    - Applies EXIF orientation before saving.
    - Preserves display dimensions after iPhone/HEIC rotation.
    - Uses high-quality JPEG settings to avoid visible degradation.
    - Uses 4:4:4 chroma sampling for better text, face and detail quality.
    - Preserves ICC profile when available.
    - Saves through Django storage so it works with local or remote storage.
    """
    temp_input_path = None
    temp_output_path = None

    try:
        if os.path.isabs(source_path):
            source_path = os.path.relpath(
                source_path,
                settings.MEDIA_ROOT,
            )

        source_path = str(source_path).lstrip("/")

        with default_storage.open(source_path, "rb") as source_file:
            suffix = os.path.splitext(source_path)[1] or ".img"

            with NamedTemporaryFile(
                delete=False,
                suffix=suffix,
            ) as temp_input:
                temp_input.write(source_file.read())
                temp_input.flush()
                temp_input_path = temp_input.name

        _, relative_path = get_converted_path(
            instance,
            source_path,
            fileupload,
            ".jpg",
        )

        with Image.open(temp_input_path) as image:
            # Critical for iPhone / HEIC / rotated JPEG files.
            image = ImageOps.exif_transpose(image)

            icc_profile = image.info.get("icc_profile")
            image = _normalized_rgb_image(image)

            with NamedTemporaryFile(
                delete=False,
                suffix=".jpg",
            ) as temp_output:
                temp_output_path = temp_output.name

            save_kwargs = {
                "format": "JPEG",
                "quality": 95,
                "optimize": True,
                "progressive": True,
                "subsampling": 0,
            }

            if icc_profile:
                save_kwargs["icc_profile"] = icc_profile

            image.save(
                temp_output_path,
                **save_kwargs,
            )

        with open(temp_output_path, "rb") as file:
            saved_key = default_storage.save(
                str(relative_path).lstrip("/"),
                File(file),
            )

        logger.info(
            "✅ Image converted to high-quality normalized JPG: %s",
            saved_key,
        )

        return str(saved_key).lstrip("/")

    except Exception as exc:
        logger.exception(
            "❌ Image conversion failed: %s",
            exc,
        )
        raise

    finally:
        for path in (
            temp_input_path,
            temp_output_path,
        ):
            try:
                if path and os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass