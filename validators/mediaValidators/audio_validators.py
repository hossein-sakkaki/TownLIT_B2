# validators/audio_validator.py

from __future__ import annotations

import mimetypes
import os
import shutil
from tempfile import NamedTemporaryFile

import ffmpeg
from django.core.exceptions import ValidationError

from validators.mime_type_validator import validate_file_type


# Compressed/lossless codecs explicitly supported as upload sources.
#
# PCM is handled separately through the "pcm_" prefix because FFmpeg
# exposes many valid PCM variants such as pcm_s16le, pcm_s24le,
# pcm_s32le and pcm_f32le.
ALLOWED_AUDIO_CODECS = frozenset(
    {
        "aac",
        "mp3",
        "vorbis",
        "opus",
        "flac",
        "alac",
    }
)


def _is_allowed_audio_codec(codec: str) -> bool:
    codec = (codec or "").strip().lower()

    if not codec:
        return False

    return codec in ALLOWED_AUDIO_CODECS or codec.startswith("pcm_")


def _is_attached_picture_stream(stream: dict) -> bool:
    disposition = stream.get("disposition") or {}

    try:
        return int(disposition.get("attached_pic") or 0) == 1
    except (TypeError, ValueError):
        return False


def _safe_probe_filelike_to_path(value) -> str:
    """
    Copy an uploaded file to a temporary local path for ffprobe.

    The original file position is restored so validation never consumes
    the upload before Django saves it.
    """

    file_obj = getattr(value, "file", value)
    suffix = os.path.splitext(getattr(value, "name", "") or "upload")[1]

    original_position = None

    try:
        if hasattr(file_obj, "tell"):
            original_position = file_obj.tell()
    except Exception:
        original_position = None

    try:
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)

        with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file_obj, tmp, length=1024 * 1024)
            return tmp.name

    finally:
        try:
            if hasattr(file_obj, "seek"):
                file_obj.seek(
                    original_position
                    if original_position is not None
                    else 0
                )
        except Exception:
            pass


def validate_audio_file(value):
    """
    Validate a real audio upload using ffprobe as the final authority.

    Supported source families include:
    - MP3
    - AAC / M4A
    - Ogg Vorbis
    - WebM / Opus
    - FLAC
    - ALAC
    - WAV / PCM, including 16/24/32-bit and float PCM variants

    Browser-recorded audio-only WebM remains supported even when the
    browser reports its MIME type as video/webm.
    """

    content_type = (
        (getattr(value, "content_type", "") or "")
        .split(";", 1)[0]
        .strip()
        .lower()
    )
    name = getattr(value, "name", "") or ""
    _, extension = os.path.splitext(name.lower())

    kind = validate_file_type(name, content_type)

    # Browsers commonly report audio-only WebM as video/webm.
    if kind != "audio" and extension == ".webm":
        kind = "audio"

    if kind != "audio":
        guessed_type, _ = mimetypes.guess_type(name)
        guessed_type = (
            (guessed_type or "")
            .split(";", 1)[0]
            .strip()
            .lower()
        )

        if validate_file_type(name, guessed_type) != "audio":
            raise ValidationError("Only audio files are allowed.")

    tmp_path = None
    created_temp_file = False

    try:
        if hasattr(value, "temporary_file_path"):
            tmp_path = value.temporary_file_path()
        else:
            tmp_path = _safe_probe_filelike_to_path(value)
            created_temp_file = True

        probe = ffmpeg.probe(tmp_path)
        streams = probe.get("streams") or []

        audio_stream = next(
            (
                stream
                for stream in streams
                if stream.get("codec_type") == "audio"
            ),
            None,
        )

        if audio_stream is None:
            raise ValidationError("No audio stream found.")

        # Reject disguised video files while still allowing embedded
        # album artwork inside legitimate audio containers.
        real_video_streams = [
            stream
            for stream in streams
            if (
                stream.get("codec_type") == "video"
                and not _is_attached_picture_stream(stream)
            )
        ]

        if real_video_streams:
            raise ValidationError(
                "Video streams are not allowed in an audio upload."
            )

        codec = (audio_stream.get("codec_name") or "").strip().lower()

        if not _is_allowed_audio_codec(codec):
            raise ValidationError(
                f"Unsupported audio codec: {codec or 'unknown'}"
            )

    except ValidationError:
        raise

    except ffmpeg.Error:
        raise ValidationError("Invalid audio file (probe failed).")

    except Exception:
        raise ValidationError("Invalid audio file (probe failed).")

    finally:
        if created_temp_file and tmp_path:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass