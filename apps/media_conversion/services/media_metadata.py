# apps/media_conversion/services/media_metadata.py

from __future__ import annotations

import json
import subprocess
from fractions import Fraction

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
        normalized_key = str(key).lstrip("/") if key else ""
        if normalized_key and default_storage.exists(normalized_key):
            return int(default_storage.size(normalized_key) or 0)
    except Exception:
        pass

    return 0


def image_metadata_from_storage(key: str) -> dict:
    """
    Read normalized image dimensions from storage.

    The converter already applies EXIF transpose. We still apply it here as
    a safety net for legacy/non-normalized images.
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


def video_metadata_from_local(path: str) -> dict:
    """
    Probe display dimensions and duration from a local video file.
    """

    stream_cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        (
            "stream=width,height,sample_aspect_ratio,display_aspect_ratio:"
            "stream_tags=rotate:"
            "stream_side_data_list"
        ),
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

    width, height = display_dimensions_from_stream(stream)

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

    return payload


def display_dimensions_from_stream(stream: dict) -> tuple[int | None, int | None]:
    """
    Resolve display dimensions from coded size + rotation + SAR/DAR.

    Returns dimensions that the frontend should use for aspect-ratio layout.
    """

    coded_width = positive_int(stream.get("width"))
    coded_height = positive_int(stream.get("height"))

    if not coded_width or not coded_height:
        return None, None

    width = coded_width
    height = coded_height

    rotation = normalized_rotation(stream)

    if rotation in {90, 270}:
        width, height = height, width

    dar = ratio_string_to_float(stream.get("display_aspect_ratio"))
    sar = ratio_string_to_float(stream.get("sample_aspect_ratio"))

    # If display_aspect_ratio exists and is meaningful, adjust display width.
    if dar and height:
        adjusted_width = int(round(height * dar))

        if adjusted_width > 0:
            width = adjusted_width

    # If there is no DAR but SAR is non-square, adjust width.
    elif sar and sar > 0 and abs(sar - 1.0) > 0.001:
        adjusted_width = int(round(width * sar))

        if adjusted_width > 0:
            width = adjusted_width

    return positive_int(width), positive_int(height)


def ratio_string_to_float(value) -> float | None:
    if not value:
        return None

    text = str(value).strip()

    if not text or text in {"0:1", "N/A"}:
        return None

    try:
        if ":" in text:
            return float(Fraction(text))

        return float(text)
    except Exception:
        return None


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

    try:
        rotation = stream.get("rotation")
        if rotation is not None:
            return int(round(float(rotation))) % 360
    except Exception:
        pass

    return 0