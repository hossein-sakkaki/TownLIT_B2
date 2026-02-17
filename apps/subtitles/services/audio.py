# apps/subtitles/services/audio.py

from __future__ import annotations

import os
import subprocess
import tempfile


def extract_audio_to_wav(video_path: str) -> str:
    """
    Extract mono 16k WAV for STT.
    Returns temp wav path.
    """
    tmp_dir = tempfile.mkdtemp(prefix="stt_")
    out_path = os.path.join(tmp_dir, "audio.wav")

    # Keep it STT-friendly
    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-ac", "1",
        "-ar", "16000",
        "-vn",
        out_path,
    ]
    subprocess.check_call(cmd)
    return out_path
