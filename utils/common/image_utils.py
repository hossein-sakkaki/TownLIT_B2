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


def convert_image_to_jpg(
    source_path: str,
    instance,
    fileupload: FileUpload,
) -> str:
    """
    Convert uploaded image to normalized JPEG.

    Important:
    - Applies EXIF orientation before saving.
    - This makes stored width/height match actual display orientation.
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

            if image.mode not in ("RGB",):
                image = image.convert("RGB")

            with NamedTemporaryFile(
                delete=False,
                suffix=".jpg",
            ) as temp_output:
                temp_output_path = temp_output.name

            image.save(
                temp_output_path,
                "JPEG",
                quality=88,
                optimize=True,
                progressive=True,
            )

        with open(temp_output_path, "rb") as file:
            saved_key = default_storage.save(
                str(relative_path).lstrip("/"),
                File(file),
            )

        logger.info(
            "✅ Image converted to normalized JPG: %s",
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