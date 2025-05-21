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
    try:
        output_abs_path, relative_path = get_converted_path(instance, source_path, fileupload, ".jpg")
        os.makedirs(os.path.dirname(output_abs_path), exist_ok=True)

        with Image.open(source_path) as image:
            rgb_image = image.convert("RGB")
            rgb_image.save(output_abs_path, "JPEG", quality=85)

        logger.info(f"✅ Image converted to JPG: {output_abs_path}")
        return relative_path

    except Exception as e:
        logger.error(f"❌ Image conversion failed (safely caught): {e}")
        return source_path.replace(settings.MEDIA_ROOT + "/", "") 

