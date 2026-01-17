# main/utils/image_utils.py

import os
import logging
from PIL import Image, ImageFile
import pillow_heif
from django.conf import settings
from utils.common.utils import FileUpload, get_converted_path
from django.core.files.base import File
from django.core.files.storage import default_storage
from tempfile import NamedTemporaryFile

pillow_heif.register_heif_opener()
ImageFile.LOAD_TRUNCATED_IMAGES = True
logger = logging.getLogger(__name__)

def convert_image_to_jpg(source_path: str, instance, fileupload: FileUpload) -> str:
    try:
        if os.path.isabs(source_path):
            source_path = os.path.relpath(source_path, settings.MEDIA_ROOT)

        # Read from storage into a temp file
        with default_storage.open(source_path, 'rb') as source_file:
            with NamedTemporaryFile(delete=False, suffix=os.path.splitext(source_path)[1]) as temp_input:
                temp_input.write(source_file.read())
                temp_input.flush()
                temp_input_path = temp_input.name
        output_abs_path, relative_path = get_converted_path(instance, source_path, fileupload, ".jpg")
        os.makedirs(os.path.dirname(output_abs_path), exist_ok=True)

        with Image.open(temp_input_path) as image:
            rgb_image = image.convert("RGB")
            rgb_image.save(output_abs_path, "JPEG", quality=85)

        logger.info(f"✅ Image converted to JPG: {output_abs_path}")

        with open(output_abs_path, 'rb') as f:
            default_storage.save(relative_path, File(f))

        return relative_path

    except Exception as e:
        logger.error(f"❌ Image conversion failed: {e}")
        raise

    finally:
        # Clean up temp files
        for path in [locals().get("temp_input_path"), locals().get("output_abs_path")]:
            if path and os.path.exists(path):
                os.remove(path)
