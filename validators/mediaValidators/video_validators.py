import os
import ffmpeg
import mimetypes
from math import floor, ceil
from fractions import Fraction
from tempfile import NamedTemporaryFile

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import TemporaryUploadedFile

from validators.mime_type_validator import validate_file_type
from validators.mediaValidators.ugc_policies import (
    MOMENT_VIDEO_POLICY,
    TESTIMONY_VIDEO_POLICY,
    VideoPolicy,
    compute_max_allowed_mb,
)

MIN_FRAME_RATE = 24
MAX_FRAME_RATE = 60


def _format_mb(bytes_size: int) -> float:
    return round((bytes_size / 1024 / 1024) * 10) / 10


def _parse_frame_rate(r_frame_rate: str) -> float:
    try:
        return float(Fraction(r_frame_rate))
    except Exception:
        raise ValidationError("Unable to read video frame rate.")


def _extract_duration_sec(probe: dict, stream: dict) -> float:
    dur = None
    try:
        fmt = probe.get("format") or {}
        dur = fmt.get("duration", None)
    except Exception:
        dur = None

    if dur is None:
        dur = stream.get("duration", None)

    try:
        dur_f = float(dur)
    except Exception:
        dur_f = 0.0

    if not dur_f or dur_f <= 0:
        raise ValidationError("Unable to read video length. Please try another file.")

    return dur_f


def validate_video_file(value, policy: VideoPolicy = MOMENT_VIDEO_POLICY):
    """
    General video validator:
    - type guard
    - ffprobe (duration + framerate)
    - duration policy
    - size policy (dynamic per duration; supports tiers)

    Default policy is Moment (so existing Moment imports keep working).
    """

    mime_type, _ = mimetypes.guess_type(value.name)
    file_type = validate_file_type(value.name, mime_type)
    if file_type != "video":
        raise ValidationError("Only video files are allowed.")

    temp_file_path = None
    is_temp_file = False

    try:
        # ensure ffprobe has a filesystem path
        if isinstance(value, TemporaryUploadedFile):
            temp_file_path = value.temporary_file_path()
        else:
            temp_file = NamedTemporaryFile(delete=False, suffix=".mp4")
            for chunk in value.chunks():
                temp_file.write(chunk)
            temp_file.flush()
            temp_file_path = temp_file.name
            temp_file.close()
            is_temp_file = True

        probe = ffmpeg.probe(temp_file_path)

        stream = next(
            (s for s in (probe.get("streams") or []) if s.get("codec_type") == "video"),
            None,
        )
        if not stream:
            raise ValidationError("No valid video stream found.")

        # frame rate check (your existing constraint)
        r_frame_rate = stream.get("r_frame_rate") or ""
        frame_rate = _parse_frame_rate(r_frame_rate)

        if frame_rate < MIN_FRAME_RATE or frame_rate > MAX_FRAME_RATE:
            raise ValidationError(
                f"Frame rate {frame_rate:.2f} is not supported (must be between {MIN_FRAME_RATE} and {MAX_FRAME_RATE})."
            )

        # duration
        duration_sec = _extract_duration_sec(probe, stream)

        if duration_sec < policy.min_duration_sec:
            raise ValidationError(
                f"Video is too short ({floor(duration_sec)}s). Minimum is {policy.min_duration_sec}s."
            )

        if duration_sec > policy.max_duration_sec:
            raise ValidationError(
                f"Video is too long ({ceil(duration_sec)}s). Maximum is {policy.max_duration_sec}s."
            )

        # size policy
        try:
            size_bytes = int(getattr(value, "size", 0) or 0)
        except Exception:
            size_bytes = 0

        if size_bytes <= 0:
            raise ValidationError("Unable to read video size. Please try another file.")

        size_mb = _format_mb(size_bytes)
        max_allowed_mb = compute_max_allowed_mb(duration_sec, policy)

        if max_allowed_mb <= 0:
            # defensive (shouldn't happen unless tiers mismatch)
            raise ValidationError("Video policy configuration error.")

        if size_mb > max_allowed_mb:
            raise ValidationError(
                f"Video is too large ({size_mb}MB). For a {round(duration_sec)}s video, max allowed is {max_allowed_mb}MB."
            )

    except ValidationError:
        raise
    except Exception as e:
        raise ValidationError(f"Video validation error: {str(e)}")
    finally:
        if is_temp_file and temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


# -------------------------------------------------
# Optional wrappers (nice & explicit for models)
# -------------------------------------------------
def validate_moment_video_file(value):
    return validate_video_file(value, policy=MOMENT_VIDEO_POLICY)


def validate_testimony_video_file(value):
    return validate_video_file(value, policy=TESTIMONY_VIDEO_POLICY)
