# apps/media_conversion/services/video_preview.py

from __future__ import annotations

import os
import subprocess

from django.core.files.base import File
from django.core.files.storage import default_storage

from apps.media_conversion.services.media_metadata import (
    video_metadata_from_local,
    storage_size,
)


def build_video_preview_mp4(
    *,
    local_source_path: str,
    output_key: str,
    seconds: float = 4.5,
    width: int = 360,
) -> dict:
    """
    Build a short muted MP4 preview for fast Stream/Square/Profile autoplay.

    Important:
    - This does not replace user uploaded thumbnails.
    - Output uses faststart for streaming.
    - Stored object is explicitly marked as video/mp4.
    """

    local_output = f"/tmp/video_preview_{os.getpid()}.mp4"

    vf = ",".join(
        [
            f"scale={width}:-2:flags=lanczos",
            "setsar=1",
            "format=yuv420p",
        ]
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-i",
        local_source_path,
        "-t",
        str(seconds),
        "-an",
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "26",
        "-profile:v",
        "high",
        "-level",
        "4.1",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        local_output,
    ]

    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        saved_key = save_mp4_with_content_type(
            local_path=local_output,
            output_key=str(output_key).lstrip("/"),
        )

        meta = video_metadata_from_local(local_output)
        meta.update(
            {
                "key": str(saved_key).lstrip("/"),
                "mime_type": "video/mp4",
                "size": storage_size(saved_key),
            }
        )

        return meta

    finally:
        if os.path.exists(local_output):
            os.remove(local_output)


def save_mp4_with_content_type(
    *,
    local_path: str,
    output_key: str,
) -> str:
    """
    Save MP4 with explicit content type.

    S3/CloudFront/AVPlayer are sensitive to Content-Type for direct preview
    playback.
    """

    output_key = str(output_key).lstrip("/")

    with open(local_path, "rb") as file:
        wrapped_file = File(
            file,
            name=os.path.basename(output_key),
        )

        # S3-compatible storages can persist this as object metadata.
        wrapped_file.content_type = "video/mp4"

        saved_key = default_storage.save(
            output_key,
            wrapped_file,
        )

    return str(saved_key).lstrip("/")