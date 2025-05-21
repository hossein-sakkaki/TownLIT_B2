# main/utils/image_utils.py

import os
import uuid
import logging
from PIL import Image, ImageFile
import pillow_heif
from django.conf import settings
from utils.common.utils import FileUpload, get_converted_path

pillow_heif.register_heif_opener()
ImageFile.LOAD_TRUNCATED_IMAGES = True

logger = logging.getLogger(__name__)


def convert_image_to_jpg(source_path: str, instance, fileupload: FileUpload) -> str:
    """
    Converts any supported image to JPG and saves it in the correct FileUpload structure.
    """
    from PIL import Image
    import pillow_heif

    pillow_heif.register_heif_opener()

    try:
        output_abs_path, relative_path = get_converted_path(instance, source_path, fileupload, ".jpg")

        os.makedirs(os.path.dirname(output_abs_path), exist_ok=True)

        image = Image.open(source_path)
        rgb_image = image.convert("RGB")
        rgb_image.save(output_abs_path, "JPEG", quality=85)

        logger.info(f"✅ Image converted to JPG: {output_abs_path}")
        return relative_path  # return relative path for model field

    except Exception as e:
        logger.error(f"❌ Image conversion failed: {e}")
        raise RuntimeError(f"Image conversion failed: {e}")
