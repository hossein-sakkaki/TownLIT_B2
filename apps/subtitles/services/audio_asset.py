# apps/subtitles/services/audio_asset.py

from __future__ import annotations

import os
import subprocess
import tempfile

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from apps.subtitles.services.hls_materializer import materialize_hls_master_to_local


def build_stt_audio_from_source_video(*, source_path: str, out_rel_path: str) -> str:
    """
    Extract mono 16k audio and store in storage.

    Supports:
      - direct video files (mp4/mov/...)
      - HLS master playlist (.m3u8) in private storage (downloads playlists+segments locally)
    """
    if not source_path:
        raise ValueError("source_path is empty")

    if not default_storage.exists(source_path):
        raise FileNotFoundError(f"Source missing: {source_path}")

    with tempfile.TemporaryDirectory(prefix="stt_audio_") as tmp:
        out_path = os.path.join(tmp, "audio.wav")

        # If HLS, materialize locally so ffmpeg can read segments without HTTP auth issues.
        if source_path.endswith(".m3u8"):
            with materialize_hls_master_to_local(source_path) as local_master:
                cmd = [
                    "ffmpeg", "-y",
                    "-protocol_whitelist", "file,crypto,data",
                    "-allowed_extensions", "ALL",
                    "-i", local_master,
                    "-vn",
                    "-ac", "1",
                    "-ar", "16000",
                    out_path,
                ]
                subprocess.check_call(cmd)
        else:
            # For normal files, download single object locally then run ffmpeg.
            local_in = os.path.join(tmp, "input")
            with default_storage.open(source_path, "rb") as rf, open(local_in, "wb") as wf:
                while True:
                    chunk = rf.read(1024 * 1024)
                    if not chunk:
                        break
                    wf.write(chunk)

            cmd = [
                "ffmpeg", "-y",
                "-i", local_in,
                "-vn",
                "-ac", "1",
                "-ar", "16000",
                out_path,
            ]
            subprocess.check_call(cmd)

        with open(out_path, "rb") as f:
            default_storage.save(out_rel_path, ContentFile(f.read()))

    return out_rel_path
