# utils/common/audio_utils.py

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from tempfile import NamedTemporaryFile

from django.conf import settings
from django.core.files.base import File
from django.core.files.storage import default_storage

from utils.common.utils import FileUpload, get_converted_path


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Canonical TownLIT audio delivery profile
# ---------------------------------------------------------------------

AUDIO_MP3_BITRATE = str(
    getattr(settings, "MEDIA_AUDIO_MP3_BITRATE", "320k")
)

AUDIO_SAMPLE_RATE_HZ = int(
    getattr(settings, "MEDIA_AUDIO_SAMPLE_RATE_HZ", 48000)
)

AUDIO_CHANNELS = int(
    getattr(settings, "MEDIA_AUDIO_CHANNELS", 2)
)

AUDIO_CONVERSION_TIMEOUT_SECONDS = int(
    getattr(settings, "MEDIA_AUDIO_CONVERSION_TIMEOUT_SECONDS", 1800)
)


@dataclass(frozen=True)
class AudioConversionResult:
    storage_path: str
    duration_ms: int
    mime_type: str
    codec: str
    container: str
    bitrate_kbps: int | None
    sample_rate_hz: int | None
    channels: int | None
    file_size_bytes: int
    checksum_sha256: str


# ---------------------------------------------------------------------
# Probe helpers
# ---------------------------------------------------------------------

def _safe_int(value) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _probe_audio_path(path: str) -> dict:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        (
            "stream=codec_name,sample_rate,channels,bit_rate:"
            "format=format_name,duration,bit_rate"
        ),
        "-of",
        "json",
        path,
    ]

    completed = subprocess.run(
        command,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=60,
    )

    payload = json.loads(
        completed.stdout.decode("utf-8", errors="replace")
    )

    streams = payload.get("streams") or []

    if not streams:
        raise ValueError("Converted output contains no audio stream.")

    stream = streams[0]
    format_info = payload.get("format") or {}

    duration_seconds = float(format_info.get("duration") or 0)

    if duration_seconds <= 0:
        raise ValueError(
            "Converted output has an invalid audio duration."
        )

    stream_bitrate = _safe_int(stream.get("bit_rate"))
    format_bitrate = _safe_int(format_info.get("bit_rate"))
    bitrate = stream_bitrate or format_bitrate

    return {
        "duration_ms": int(round(duration_seconds * 1000)),
        "codec": (stream.get("codec_name") or "").lower(),
        "container": (format_info.get("format_name") or "").split(",", 1)[0],
        "bitrate_kbps": (
            int(round(bitrate / 1000))
            if bitrate
            else None
        ),
        "sample_rate_hz": _safe_int(stream.get("sample_rate")),
        "channels": _safe_int(stream.get("channels")),
    }


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()

    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def _validate_canonical_mp3(metadata: dict) -> None:
    if metadata["codec"] != "mp3":
        raise ValueError(
            "Audio conversion did not produce the expected MP3 codec."
        )

    if metadata["sample_rate_hz"] != AUDIO_SAMPLE_RATE_HZ:
        raise ValueError(
            "Audio conversion produced an unexpected sample rate: "
            f"{metadata['sample_rate_hz']} Hz."
        )

    if metadata["channels"] != AUDIO_CHANNELS:
        raise ValueError(
            "Audio conversion produced an unexpected channel count: "
            f"{metadata['channels']}."
        )

    if metadata["duration_ms"] <= 0:
        raise ValueError(
            "Audio conversion produced an invalid duration."
        )


# ---------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------

def convert_audio_to_mp3_with_metadata(
    source_path: str,
    instance,
    fileupload: FileUpload,
) -> AudioConversionResult:
    """
    Convert any validated audio source into the canonical TownLIT
    playback profile.

    Canonical delivery output:
    - MP3
    - libmp3lame
    - 320 kbps
    - 48 kHz
    - stereo
    - highest encoder algorithm quality
    - no artistic EQ, compression or loudness normalization

    The source mix/master is therefore not artistically altered.
    """

    temp_input_path = None
    output_abs_path = None

    try:
        if os.path.isabs(source_path):
            source_path = os.path.relpath(
                source_path,
                settings.MEDIA_ROOT,
            )

        suffix = os.path.splitext(source_path)[1] or ".audio"

        with default_storage.open(source_path, "rb") as source_file:
            with NamedTemporaryFile(
                delete=False,
                suffix=suffix,
            ) as temp_input:
                shutil.copyfileobj(
                    source_file,
                    temp_input,
                    length=1024 * 1024,
                )
                temp_input.flush()
                temp_input_path = temp_input.name

        output_abs_path, relative_path = get_converted_path(
            instance,
            source_path,
            fileupload,
            ".mp3",
        )

        os.makedirs(
            os.path.dirname(output_abs_path),
            exist_ok=True,
        )

        command = [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",

            "-i",
            temp_input_path,

            # Use exactly the first audio stream and discard any
            # attached/non-audio streams from the delivery file.
            "-map",
            "0:a:0",
            "-vn",
            "-sn",
            "-dn",

            # Produce deterministic clean delivery assets.
            "-map_metadata",
            "-1",

            # Canonical TownLIT playback encoding.
            "-codec:a",
            "libmp3lame",
            "-b:a",
            AUDIO_MP3_BITRATE,
            "-compression_level",
            "0",
            "-ar",
            str(AUDIO_SAMPLE_RATE_HZ),
            "-ac",
            str(AUDIO_CHANNELS),

            # Improve duration/seek compatibility for clients.
            "-write_xing",
            "1",

            output_abs_path,
        ]

        completed = subprocess.run(
            command,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=AUDIO_CONVERSION_TIMEOUT_SECONDS,
        )

        if not os.path.exists(output_abs_path):
            raise RuntimeError(
                "FFmpeg completed but the converted audio file "
                "was not created."
            )

        metadata = _probe_audio_path(output_abs_path)
        _validate_canonical_mp3(metadata)

        file_size_bytes = os.path.getsize(output_abs_path)
        checksum_sha256 = _sha256_file(output_abs_path)

        with open(output_abs_path, "rb") as file:
            saved_path = default_storage.save(
                relative_path,
                File(file),
            )

        logger.info(
            (
                "Audio converted to canonical MP3: "
                "path=%s duration_ms=%s bitrate_kbps=%s "
                "sample_rate=%s channels=%s"
            ),
            saved_path,
            metadata["duration_ms"],
            metadata["bitrate_kbps"],
            metadata["sample_rate_hz"],
            metadata["channels"],
        )

        return AudioConversionResult(
            storage_path=saved_path,
            duration_ms=metadata["duration_ms"],
            mime_type="audio/mpeg",
            codec="mp3",
            container="mp3",
            bitrate_kbps=metadata["bitrate_kbps"],
            sample_rate_hz=metadata["sample_rate_hz"],
            channels=metadata["channels"],
            file_size_bytes=file_size_bytes,
            checksum_sha256=checksum_sha256,
        )

    except subprocess.TimeoutExpired as exc:
        logger.error(
            "Audio conversion timed out after %s seconds",
            AUDIO_CONVERSION_TIMEOUT_SECONDS,
        )
        raise RuntimeError("Audio conversion timed out.") from exc

    except subprocess.CalledProcessError as exc:
        stderr = (
            (exc.stderr or b"")
            .decode(errors="ignore")
            .strip()
        )

        logger.error(
            "Audio conversion failed: %s",
            stderr,
        )

        raise RuntimeError(
            "FFmpeg failed to convert the audio file."
        ) from exc

    finally:
        for path in (temp_input_path, output_abs_path):
            try:
                if path and os.path.exists(path):
                    os.remove(path)
            except Exception:
                logger.warning(
                    "Failed to remove temporary audio file: %s",
                    path,
                )


def convert_audio_to_mp3(
    source_path: str,
    instance,
    fileupload: FileUpload,
) -> str:
    """
    Backward-compatible public API.

    Existing callers throughout TownLIT continue receiving only the
    converted storage path exactly as before.
    """

    return convert_audio_to_mp3_with_metadata(
        source_path,
        instance,
        fileupload,
    ).storage_path