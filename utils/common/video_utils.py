# /utils/common/video_utils.py

import os
import subprocess
from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage
from django.core.files import File

from utils.common.utils import FileUpload, get_converted_path
import logging
from django.core.files.storage import default_storage
from tempfile import NamedTemporaryFile

logger = logging.getLogger(__name__)

def convert_video_to_mp4(source_path: str, instance, fileupload: FileUpload) -> str:
    try:
        # تبدیل مسیر absolute به relative در صورت نیاز
        if os.path.isabs(source_path):
            source_path = os.path.relpath(source_path, settings.MEDIA_ROOT)

        # دانلود فایل ورودی (از S3 یا لوکال)
        with default_storage.open(source_path, 'rb') as source_file:
            with NamedTemporaryFile(delete=False, suffix=os.path.splitext(source_path)[1]) as temp_input:
                temp_input.write(source_file.read())
                temp_input.flush()
                temp_input_path = temp_input.name

        # تولید مسیر خروجی
        output_abs_path, relative_path = get_converted_path(instance, source_path, fileupload, ".mp4")
        os.makedirs(os.path.dirname(output_abs_path), exist_ok=True)

        # اجرای FFmpeg
        command = [
            "ffmpeg",
            "-y",
            "-i", temp_input_path,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-g", "48",
            "-keyint_min", "24",
            "-sc_threshold", "0",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            output_abs_path,
        ]
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
        logger.info(f"✅ Video converted to MP4: {output_abs_path}")

        # آپلود فایل به default_storage (محلی یا S3)
        with open(output_abs_path, 'rb') as f:
            default_storage.save(relative_path, File(f))

        # حذف فایل‌های موقت
        os.remove(temp_input_path)
        os.remove(output_abs_path)

        return relative_path

    except subprocess.CalledProcessError as e:
        logger.warning(f"⚠️ FFmpeg conversion failed: {e.stderr.decode(errors='ignore').strip()}")
        if isinstance(default_storage, S3Boto3Storage):
            return source_path  # در S3، مسیر از ابتدا relative بوده است
        else:
            return os.path.relpath(source_path, settings.MEDIA_ROOT)
   