# /utils/common/video_utils.py

import os
import subprocess
from django.conf import settings
from django.core.files import File

from utils.common.utils import FileUpload, get_hls_output_dir
import logging
from django.core.files.storage import default_storage
from tempfile import NamedTemporaryFile

logger = logging.getLogger(__name__)


# Video Convert to Multi HLS -------------------------------------------------------------------------   
def convert_video_to_multi_hls(source_path: str, instance, fileupload: FileUpload) -> str:
    temp_input_path = None
    output_dir = None
    master_playlist_storage_path = None

    try:
        if os.path.isabs(source_path):
            source_path = os.path.relpath(source_path, settings.MEDIA_ROOT)

        with default_storage.open(source_path, 'rb') as source_file:
            with NamedTemporaryFile(delete=False, suffix=os.path.splitext(source_path)[1]) as temp_input:
                temp_input.write(source_file.read())
                temp_input.flush()
                temp_input_path = temp_input.name

        output_dir, relative_dir = get_hls_output_dir(instance, fileupload)
        os.makedirs(output_dir, exist_ok=True)

        # ✅ ترتیب لیست‌شده از بالاترین کیفیت به پایین‌ترین
        renditions = [
            ("1080p", "1920x1080", "5000000"),
            ("720p", "1280x720", "3000000"),
            ("480p", "854x480", "1000000"),
        ]

        master_playlist_local_path = os.path.join(output_dir, "master.m3u8")
        variant_playlists = []

        for label, resolution, bandwidth in renditions:
            subdir = os.path.join(output_dir, label)
            os.makedirs(subdir, exist_ok=True)
            playlist_path = os.path.join(subdir, "playlist.m3u8")

            command = [
                "ffmpeg", "-y",
                "-i", temp_input_path,
                "-vf", f"scale={resolution}",
                "-c:a", "aac", "-b:a", "96k",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
                "-f", "hls",
                "-hls_time", "5",
                "-hls_playlist_type", "vod",
                "-hls_segment_filename", os.path.join(subdir, "segment_%03d.ts"),
                playlist_path
            ]

            subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
            variant_playlists.append((label, resolution, bandwidth, os.path.join(label, "playlist.m3u8")))

        # ✅ نوشتن master.m3u8 با ترتیب درست
        with open(master_playlist_local_path, "w") as master:
            master.write("#EXTM3U\n")
            for label, resolution, bandwidth, path in variant_playlists:
                width, height = resolution.split("x")
                master.write(f"#EXT-X-STREAM-INF:BANDWIDTH={bandwidth},RESOLUTION={width}x{height}\n")
                master.write(f"{path}\n")

        # ✅ آپلود همه فایل‌ها
        for root, _, files in os.walk(output_dir):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.join(relative_dir, os.path.relpath(full_path, output_dir))
                with open(full_path, 'rb') as f:
                    default_storage.save(rel_path, File(f))

                if os.path.basename(full_path) == "master.m3u8":
                    master_playlist_storage_path = rel_path

        if not master_playlist_storage_path:
            raise FileNotFoundError("master.m3u8 was not uploaded correctly.")

        return master_playlist_storage_path

    except subprocess.CalledProcessError as e:
        logger.warning(f"⚠️ FFmpeg HLS conversion failed: {e.stderr.decode(errors='ignore').strip()}")
        raise

    finally:
        if temp_input_path and os.path.exists(temp_input_path):
            os.remove(temp_input_path)
        if output_dir and os.path.exists(output_dir):
            import shutil
            shutil.rmtree(output_dir)

