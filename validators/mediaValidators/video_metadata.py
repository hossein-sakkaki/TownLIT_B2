# validators/mediaValidators/video_metadata.py

import os
import tempfile
import subprocess
from typing import Optional, Tuple


class VideoMetadataError(Exception):
    pass


def _file_to_path(uploaded_file) -> Tuple[str, Optional[str]]:
    """
    Returns (path, tmp_path_to_cleanup_or_none)
    - If TemporaryUploadedFile: use its temp path (no cleanup needed here).
    - If InMemoryUploadedFile: write to a NamedTemporaryFile and return its path + cleanup path.
    """
    # TemporaryUploadedFile in Django has temporary_file_path()
    if hasattr(uploaded_file, "temporary_file_path"):
        return uploaded_file.temporary_file_path(), None

    # Otherwise write to a temp file
    suffix = ""
    name = getattr(uploaded_file, "name", "") or ""
    if "." in name:
        suffix = "." + name.split(".")[-1].lower()

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_path = tmp.name
    try:
        for chunk in uploaded_file.chunks():
            tmp.write(chunk)
        tmp.flush()
    finally:
        tmp.close()

    return tmp_path, tmp_path


def get_video_duration_seconds(uploaded_file, timeout_sec: int = 6) -> float:
    """
    Uses ffprobe to extract duration (seconds) from a file.
    Raises VideoMetadataError on failure.
    """
    path, cleanup_path = _file_to_path(uploaded_file)
    try:
        # metadata-only read (fast)
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )

        if proc.returncode != 0:
            raise VideoMetadataError("ffprobe failed")

        raw = (proc.stdout or "").strip()
        try:
            dur = float(raw)
        except Exception:
            raise VideoMetadataError("invalid duration")

        if not (dur > 0.0):
            raise VideoMetadataError("non-positive duration")

        return dur

    except subprocess.TimeoutExpired:
        raise VideoMetadataError("ffprobe timeout")
    finally:
        if cleanup_path and os.path.exists(cleanup_path):
            try:
                os.remove(cleanup_path)
            except Exception:
                pass
