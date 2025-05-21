# utils/common/audio_utils.py

import os
import subprocess
import uuid
import logging
from django.conf import settings
from utils.common.utils import FileUpload, get_converted_path

logger = logging.getLogger(__name__)


def convert_audio_to_mp3(source_path: str, instance, fileupload: FileUpload) -> str:
    try:
        output_abs_path, relative_path = get_converted_path(instance, source_path, fileupload, ".mp3")
        os.makedirs(os.path.dirname(output_abs_path), exist_ok=True)

        command = [
            "ffmpeg",
            "-y",                     # Overwrite if exists
            "-i", source_path,        # Input file
            "-codec:a", "libmp3lame", # Use LAME codec
            "-qscale:a", "2",         # High quality (lower = better quality)
            output_abs_path,
        ]

        result = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            check=True
        )

        logger.info(f"✅ Audio converted to MP3: {output_abs_path}")
        return relative_path

    except subprocess.CalledProcessError as e:
        error_output = e.stderr.decode(errors="ignore").strip()
        logger.error(f"❌ Audio conversion failed:\n{error_output}")
        raise RuntimeError(f"Audio conversion failed: {e}")
