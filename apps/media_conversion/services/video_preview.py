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
    Build a short muted MP4 preview for fast grid/profile autoplay.
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

        with open(local_output, "rb") as file:
            saved_key = default_storage.save(
                str(output_key).lstrip("/"),
                File(file),
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