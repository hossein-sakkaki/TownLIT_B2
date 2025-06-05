# utils/common/audio_utils.py

import os
import subprocess
import uuid
import logging
from storages.backends.s3boto3 import S3Boto3Storage
from django.core.files.base import File
from django.conf import settings
from utils.common.utils import FileUpload, get_converted_path

logger = logging.getLogger(__name__)

from django.core.files.storage import default_storage
from tempfile import NamedTemporaryFile



def convert_audio_to_mp3(source_path: str, instance, fileupload: FileUpload) -> str:
    try:
        # تبدیل مسیر مطلق به نسبی در صورت نیاز
        if os.path.isabs(source_path):
            source_path = os.path.relpath(source_path, settings.MEDIA_ROOT)

        # خواندن فایل از storage (لوکال یا S3)
        with default_storage.open(source_path, 'rb') as source_file:
            with NamedTemporaryFile(delete=False, suffix=os.path.splitext(source_path)[1]) as temp_input:
                temp_input.write(source_file.read())
                temp_input.flush()
                temp_input_path = temp_input.name

        # مسیر خروجی (در صورت موفقیت)
        output_abs_path, relative_path = get_converted_path(instance, source_path, fileupload, ".mp3")
        os.makedirs(os.path.dirname(output_abs_path), exist_ok=True)

        # اجرای FFmpeg
        command = [
            "ffmpeg",
            "-y",
            "-i", temp_input_path,
            "-codec:a", "libmp3lame",
            "-qscale:a", "2",
            output_abs_path,
        ]

        subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            check=True
        )

        logger.info(f"✅ Audio converted to MP3: {output_abs_path}")

        # ذخیره فایل تبدیل‌شده در storage
        with open(output_abs_path, 'rb') as f:
            default_storage.save(relative_path, File(f))

        # حذف فایل‌های موقت
        os.remove(temp_input_path)
        os.remove(output_abs_path)

        return relative_path  # ✅ همیشه فقط مسیر relative را برمی‌گردانیم

    except subprocess.CalledProcessError as e:
        error_output = e.stderr.decode(errors="ignore").strip()
        logger.error(f"❌ Audio conversion failed:\n{error_output}")

        # ✅ مسیر fallback با توجه به نوع storage
        if isinstance(default_storage, S3Boto3Storage):
            return source_path  # در S3، مسیر همیشه relative است
        else:
            return os.path.relpath(source_path, settings.MEDIA_ROOT)