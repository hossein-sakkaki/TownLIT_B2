import os
import subprocess
import uuid
from django.conf import settings
from utils.common.utils import FileUpload, get_converted_path
import logging
logger = logging.getLogger(__name__)

def convert_video_to_mp4(source_path: str, instance, fileupload: FileUpload) -> str:
    """
    Converts any video file to MP4 and saves it in the correct FileUpload path.
    Returns the relative path for saving to model field.
    """
    try:
        output_abs_path, relative_path = get_converted_path(instance, source_path, fileupload, ".mp4")

        os.makedirs(os.path.dirname(output_abs_path), exist_ok=True)

        command = [
            "ffmpeg",
            "-y",
            "-i", source_path,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-movflags", "+faststart",
            "-preset", "medium",
            "-crf", "23",
            output_abs_path,
        ]

        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        logger.info(f"✅ Video converted to MP4: {output_abs_path}")
        return relative_path

    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Video conversion failed: {e}")
        raise RuntimeError(f"Video conversion failed: {e}")
