# main/utils/image_utils.py

import os
import uuid
import logging
from PIL import Image, ImageFile
import pillow_heif
from storages.backends.s3boto3 import S3Boto3Storage
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
        # تبدیل مسیر مطلق به نسبی
        if os.path.isabs(source_path):
            source_path = os.path.relpath(source_path, settings.MEDIA_ROOT)

        # دریافت فایل از storage
        with default_storage.open(source_path, 'rb') as source_file:
            with NamedTemporaryFile(delete=False, suffix=os.path.splitext(source_path)[1]) as temp_input:
                temp_input.write(source_file.read())
                temp_input.flush()
                temp_input_path = temp_input.name

        # مسیر خروجی
        output_abs_path, relative_path = get_converted_path(instance, source_path, fileupload, ".jpg")
        os.makedirs(os.path.dirname(output_abs_path), exist_ok=True)

        # تبدیل و ذخیره JPG در مسیر موقت
        with Image.open(temp_input_path) as image:
            rgb_image = image.convert("RGB")
            rgb_image.save(output_abs_path, "JPEG", quality=85)

        logger.info(f"✅ Image converted to JPG: {output_abs_path}")

        # ذخیره فایل در storage اصلی
        with open(output_abs_path, 'rb') as f:
            default_storage.save(relative_path, File(f))

        os.remove(temp_input_path)
        os.remove(output_abs_path)

        # ✅ در حالت موفق
        return relative_path

    except Exception as e:
        logger.error(f"❌ Image conversion failed: {e}")

        # ✅ در حالت شکست، مسیر fallback بسته به نوع storage
        if isinstance(default_storage, S3Boto3Storage):
            return source_path  # در S3 مسیر از ابتدا relative است
        else:
            return os.path.relpath(source_path, settings.MEDIA_ROOT)
