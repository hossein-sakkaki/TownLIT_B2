# apps/media_conversion/services/media_metadata.py

from __future__ import annotations

import json
import os
import subprocess
import tempfile

from PIL import Image, ImageOps
from django.core.files.storage import default_storage


def positive_int(value) -> int | None:
    try:
        parsed = int(value)
    except Exception:
        return None

    return parsed if parsed > 0 else None


def positive_float(value) -> float | None:
    try:
        parsed = float(value)
    except Exception:
        return None

    return parsed if parsed > 0 else None


def aspect_payload(
    *,
    width=None,
    height=None,
    aspect_ratio=None,
) -> dict:
    width = positive_int(width)
    height = positive_int(height)
    ratio = positive_float(aspect_ratio)

    if not ratio and width and height:
        ratio = width / height

    return {
        "width": width,
        "height": height,
        "aspect_ratio": ratio,
    }


def storage_size(key: str | None) -> int:
    try:
        if key and default_storage.exists(key):
            return int(default_storage.size(key) or 0)
    except Exception:
        pass

    return 0


def image_metadata_from_storage(key: str) -> dict:
    """
    Read image dimensions once during conversion/backfill.
    """

    normalized_key = str(key).lstrip("/")

    with default_storage.open(normalized_key, "rb") as file:
        with Image.open(file) as image:
            image = ImageOps.exif_transpose(image)
            width, height = image.size

    payload = aspect_payload(
        width=width,
        height=height,
    )

    payload.update(
        {
            "key": normalized_key,
            "mime_type": "image/jpeg",
            "size": storage_size(normalized_key),
        }
    )

    return payload


def video_metadata_from_storage(key: str) -> dict:
    """
    Read video dimensions and duration from storage-backed media.

    ffprobe works with local file paths, so remote/default storage files are
    copied to a temporary local file first.
    """

    normalized_key = str(key).lstrip("/")

    suffix = os.path.splitext(normalized_key)[1] or ".mp4"
    temp_path = None

    try:
        with default_storage.open(normalized_key, "rb") as source:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                suffix=suffix,
                delete=False,
            ) as temp_file:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    if not chunk:
                        break

                    temp_file.write(chunk)

                temp_path = temp_file.name

        payload = video_metadata_from_local(temp_path)

        payload.update(
            {
                "key": normalized_key,
                "mime_type": video_mime_type_from_key(normalized_key),
                "size": storage_size(normalized_key),
            }
        )

        return payload

    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except OSError:
                pass


def video_mime_type_from_key(key: str) -> str:
    """
    Best-effort mime type from extension.

    This avoids adding a new dependency just for legacy metadata backfill.
    """

    ext = os.path.splitext(str(key).lower())[1]

    if ext in {".mov", ".qt"}:
        return "video/quicktime"

    if ext in {".m4v"}:
        return "video/x-m4v"

    if ext in {".webm"}:
        return "video/webm"

    if ext in {".m3u8"}:
        return "application/vnd.apple.mpegurl"

    return "video/mp4"


def video_metadata_from_local(path: str) -> dict:
    """
    Probe display dimensions and duration from local video file.
    """

    stream_cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height:stream_tags=rotate:stream_side_data_list",
        "-of",
        "json",
        path,
    ]

    format_cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        path,
    ]

    stream_data = json.loads(
        subprocess.check_output(stream_cmd).decode("utf-8", "ignore")
    )

    format_data = json.loads(
        subprocess.check_output(format_cmd).decode("utf-8", "ignore")
    )

    stream = (stream_data.get("streams") or [{}])[0]

    width = positive_int(stream.get("width"))
    height = positive_int(stream.get("height"))
    rotation = normalized_rotation(stream)

    if rotation in {90, 270} and width and height:
        width, height = height, width

    duration_ms = None

    try:
        duration_raw = format_data.get("format", {}).get("duration")
        duration_ms = int(float(duration_raw) * 1000) if duration_raw else None
    except Exception:
        duration_ms = None

    payload = aspect_payload(
        width=width,
        height=height,
    )

    payload["duration_ms"] = duration_ms

    if duration_ms:
        payload["duration_seconds"] = round(duration_ms / 1000, 3)

    return payload


def normalized_rotation(stream: dict) -> int:
    try:
        for item in stream.get("side_data_list") or []:
            if isinstance(item, dict) and "rotation" in item:
                return int(round(float(item.get("rotation")))) % 360
    except Exception:
        pass

    try:
        rotate = (stream.get("tags") or {}).get("rotate")
        if rotate is not None:
            return int(round(float(rotate))) % 360
    except Exception:
        pass

    return 0