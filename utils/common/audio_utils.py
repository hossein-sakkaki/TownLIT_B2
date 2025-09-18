# utils/common/audio_utils.py

import os
import subprocess
import logging
from django.core.files.base import File
from django.conf import settings
from utils.common.utils import FileUpload, get_converted_path
from django.core.files.storage import default_storage
from tempfile import NamedTemporaryFile

logger = logging.getLogger(__name__)

def convert_audio_to_mp3(source_path: str, instance, fileupload: FileUpload) -> str:
    temp_input_path = None
    output_abs_path = None
    try:
        # Normalize to storage-relative path
        if os.path.isabs(source_path):
            source_path = os.path.relpath(source_path, settings.MEDIA_ROOT)

        # Read from storage into a temp file (ffmpeg input)
        with default_storage.open(source_path, 'rb') as source_file:
            with NamedTemporaryFile(delete=False, suffix=os.path.splitext(source_path)[1]) as temp_input:
                temp_input.write(source_file.read())
                temp_input.flush()
                temp_input_path = temp_input.name

        # Build output target (local abs + storage-relative)
        output_abs_path, relative_path = get_converted_path(instance, source_path, fileupload, ".mp3")
        os.makedirs(os.path.dirname(output_abs_path), exist_ok=True)

        # Transcode to MP3 (VBR ~190kbps)
        command = [
            "ffmpeg", "-y",
            "-i", temp_input_path,
            "-codec:a", "libmp3lame",
            "-qscale:a", "2",
            output_abs_path,
        ]
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
        logger.info(f"✅ Audio converted to MP3: {output_abs_path}")

        # Upload converted file to default storage
        with open(output_abs_path, 'rb') as f:
            default_storage.save(relative_path, File(f))

        return relative_path

    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Audio conversion failed: {e.stderr.decode(errors='ignore').strip()}")
        raise
    finally:
        # Clean up temp & local outputs
        for path in (temp_input_path, output_abs_path):
            try:
                if path and os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass
