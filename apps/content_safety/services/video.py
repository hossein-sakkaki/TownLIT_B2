# apps/content_safety/services/video.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-14.
# Last Update by Hossein Sakkaki on 2026-08-14.

from __future__ import annotations

import base64
import hashlib
import json
import logging
import math
import os
import shutil
import subprocess
import tempfile

from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from dataclasses import dataclass

from django.conf import settings
from django.db import close_old_connections

from apps.content_safety.enums import (
    SafetyContext,
    SafetyDecision,
    SafetyInputType,
    SafetyReason,
    SafetyRiskLevel,
)
from apps.content_safety.exceptions import (
    ContentSafetyBlockedError,
    ContentSafetyReviewError,
    ContentSafetyUnavailableError,
)
from apps.content_safety.models import (
    ContentSafetyEvent,
)
from apps.content_safety.services.adjudication_cache import (
    cache_adjudication,
    get_cached_adjudication,
)
from apps.content_safety.services.hashing import (
    hash_safety_input,
)
from apps.content_safety.services.image import (
    check_image_safety,
)
from apps.content_safety.services.media_types import (
    VideoSafetyResult,
)
from apps.content_safety.services.normalization import (
    normalize_text_for_safety,
)
from apps.content_safety.services.text import (
    check_text_safety,
)
from apps.content_safety.services.video_transcription import (
    transcribe_video_audio,
)
from apps.content_safety.services.video_visual import (
    adjudicate_video_visual,
    inspect_video_visual_guard,
)


logger = logging.getLogger(
    __name__
)


_SUPPORTED_VIDEO_MIME_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/x-m4v",
    "video/webm",
    "video/mpeg",
    "video/3gpp",
}


_VIDEO_RESULT_SIGNAL = (
    "video_final_result"
)


_RISK_ORDER = {
    SafetyRiskLevel.LOW: 0,
    SafetyRiskLevel.MEDIUM: 1,
    SafetyRiskLevel.HIGH: 2,
    SafetyRiskLevel.CRITICAL: 3,
}


@dataclass(frozen=True)
class VideoProbe:
    duration_seconds: float
    has_video: bool
    has_audio: bool


@dataclass(frozen=True)
class VideoFrameSample:
    index: int
    image_bytes: bytes
    timestamp_seconds: float | None = None


@dataclass(frozen=True)
class VideoFrameScreening:
    frame: VideoFrameSample
    decision: str
    risk_level: str
    reason_code: str
    provider_flagged: bool


@dataclass(frozen=True)
class TranscriptSafety:
    decision: str
    risk_level: str
    reason_code: str
    input_hash: str
    chunk_count: int
    adjudicated: bool


def _media_policy_version() -> str:
    value = str(
        settings.CONTENT_SAFETY_MEDIA_POLICY_VERSION
        or ""
    ).strip()

    if not value:
        raise RuntimeError(
            "CONTENT_SAFETY_MEDIA_POLICY_VERSION is missing."
        )

    return value


def _video_pipeline_version() -> str:
    value = str(
        settings.CONTENT_SAFETY_VIDEO_PIPELINE_VERSION
        or ""
    ).strip()

    if not value:
        raise RuntimeError(
            "CONTENT_SAFETY_VIDEO_PIPELINE_VERSION is missing."
        )

    return value


def _video_result_cache_model() -> str:
    value = str(
        settings.CONTENT_SAFETY_VIDEO_RESULT_CACHE_MODEL
        or ""
    ).strip()

    if not value:
        raise RuntimeError(
            "CONTENT_SAFETY_VIDEO_RESULT_CACHE_MODEL is missing."
        )

    return value


def _normalize_context(
    value: str,
) -> str:
    context = str(
        value
        or SafetyContext.GENERIC
    ).strip()

    valid_values = {
        choice.value
        for choice in SafetyContext
    }

    if context not in valid_values:
        return SafetyContext.GENERIC

    return context


def _normalize_video_mime_type(
    value: str | None,
) -> str:
    normalized = str(
        value
        or ""
    ).strip().lower()

    if normalized in {
        "",
        "application/octet-stream",
        "binary/octet-stream",
    }:
        return ""

    if normalized not in _SUPPORTED_VIDEO_MIME_TYPES:
        raise ValueError(
            "Unsupported video type for content safety."
        )

    return normalized


def _video_suffix(
    mime_type: str,
) -> str:
    return {
        "video/mp4": ".mp4",
        "video/quicktime": ".mov",
        "video/x-m4v": ".m4v",
        "video/webm": ".webm",
        "video/mpeg": ".mpeg",
        "video/3gpp": ".3gp",
    }.get(
        mime_type,
        ".video",
    )


def _max_video_bytes() -> int:
    value = int(
        settings.CONTENT_SAFETY_MAX_VIDEO_BYTES
    )

    if value <= 0:
        raise RuntimeError(
            "CONTENT_SAFETY_MAX_VIDEO_BYTES must be positive."
        )

    return value


def _hash_video_bytes(
    video_bytes: bytes,
) -> str:
    return hashlib.sha256(
        video_bytes
    ).hexdigest()


def _jpeg_data_url(
    image_bytes: bytes,
) -> str:
    encoded = base64.b64encode(
        image_bytes
    ).decode(
        "ascii"
    )

    return (
        "data:image/jpeg;base64,"
        + encoded
    )


def _ensure_media_binaries() -> tuple[str, str]:
    ffmpeg_raw = str(
        settings.CONTENT_SAFETY_FFMPEG_BINARY
        or "ffmpeg"
    ).strip()

    ffprobe_raw = str(
        settings.CONTENT_SAFETY_FFPROBE_BINARY
        or "ffprobe"
    ).strip()

    ffmpeg = (
        shutil.which(
            ffmpeg_raw
        )
        or (
            ffmpeg_raw
            if os.path.isfile(
                ffmpeg_raw
            )
            else None
        )
    )

    ffprobe = (
        shutil.which(
            ffprobe_raw
        )
        or (
            ffprobe_raw
            if os.path.isfile(
                ffprobe_raw
            )
            else None
        )
    )

    if not ffmpeg:
        raise RuntimeError(
            "FFmpeg is unavailable."
        )

    if not ffprobe:
        raise RuntimeError(
            "FFprobe is unavailable."
        )

    return (
        ffmpeg,
        ffprobe,
    )


def _run_process(
    command: list[str],
) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=(
                settings.CONTENT_SAFETY_VIDEO_FFMPEG_TIMEOUT_SECONDS
            ),
        )

    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "Video safety media processing timed out."
        ) from exc


def _probe_video(
    *,
    path: str,
    ffprobe: str,
) -> VideoProbe:
    result = _run_process(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type",
            "-of",
            "json",
            path,
        ]
    )

    if result.returncode != 0:
        raise ValueError(
            "Video could not be inspected."
        )

    try:
        payload = json.loads(
            result.stdout.decode(
                "utf-8"
            )
        )

    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise ValueError(
            "Video metadata is invalid."
        ) from exc

    streams = payload.get(
        "streams"
    ) or []

    has_video = any(
        str(
            stream.get(
                "codec_type",
                "",
            )
        ).strip().lower()
        == "video"
        for stream in streams
        if isinstance(
            stream,
            dict,
        )
    )

    has_audio = any(
        str(
            stream.get(
                "codec_type",
                "",
            )
        ).strip().lower()
        == "audio"
        for stream in streams
        if isinstance(
            stream,
            dict,
        )
    )

    duration_raw = (
        payload.get(
            "format"
        )
        or {}
    ).get(
        "duration"
    )

    try:
        duration = float(
            duration_raw
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            "Video duration could not be determined."
        ) from exc

    if (
        not has_video
        or not math.isfinite(
            duration
        )
        or duration <= 0
    ):
        raise ValueError(
            "Invalid video media."
        )

    max_duration = float(
        settings.CONTENT_SAFETY_MAX_VIDEO_DURATION_SECONDS
    )

    if (
        max_duration > 0
        and duration > max_duration
    ):
        raise ValueError(
            "Video exceeds the content safety duration limit."
        )

    return VideoProbe(
        duration_seconds=duration,
        has_video=has_video,
        has_audio=has_audio,
    )


def _desired_uniform_frame_count(
    duration_seconds: float,
) -> int:
    if duration_seconds <= 15:
        desired = 6

    elif duration_seconds <= 30:
        desired = 8

    elif duration_seconds <= 60:
        desired = 12

    elif duration_seconds <= 180:
        desired = 12

    else:
        desired = 12

    max_frames = max(
        1,
        int(
            settings.CONTENT_SAFETY_VIDEO_MAX_FRAMES
        ),
    )

    reserved_scene_frames = (
        max(
            0,
            int(
                settings.CONTENT_SAFETY_VIDEO_MAX_SCENE_FRAMES
            ),
        )
        if settings.CONTENT_SAFETY_VIDEO_SCENE_SAMPLING_ENABLED
        else 0
    )

    max_uniform = max(
        1,
        max_frames - reserved_scene_frames,
    )

    return min(
        desired,
        max_uniform,
    )


def _uniform_timestamps(
    *,
    duration_seconds: float,
    count: int,
) -> list[float]:
    if count <= 1:
        return [
            max(
                0,
                duration_seconds / 2,
            )
        ]

    margin = min(
        0.20,
        duration_seconds * 0.02,
    )

    start = min(
        margin,
        max(
            0,
            duration_seconds / 4,
        ),
    )

    end = max(
        start,
        duration_seconds - margin,
    )

    if end <= start:
        return [
            duration_seconds / 2
        ]

    step = (
        end - start
    ) / (
        count - 1
    )

    return [
        start + (
            step * index
        )
        for index in range(
            count
        )
    ]


def _extract_one_frame(
    *,
    video_path: str,
    output_path: str,
    timestamp: float,
    ffmpeg: str,
) -> None:
    width = max(
        256,
        int(
            settings.CONTENT_SAFETY_VIDEO_FRAME_WIDTH
        ),
    )

    result = _run_process(
        [
            ffmpeg,
            "-v",
            "error",
            "-ss",
            f"{max(timestamp, 0):.3f}",
            "-i",
            video_path,
            "-frames:v",
            "1",
            "-vf",
            (
                f"scale={width}:{width}:"
                "force_original_aspect_ratio=decrease"
            ),
            "-q:v",
            "5",
            "-y",
            output_path,
        ]
    )

    if (
        result.returncode != 0
        or not os.path.isfile(
            output_path
        )
        or os.path.getsize(
            output_path
        ) <= 0
    ):
        raise ValueError(
            "Video frame extraction failed."
        )


def _extract_uniform_frames(
    *,
    video_path: str,
    duration_seconds: float,
    output_dir: str,
    ffmpeg: str,
) -> list[VideoFrameSample]:
    count = _desired_uniform_frame_count(
        duration_seconds
    )

    timestamps = _uniform_timestamps(
        duration_seconds=duration_seconds,
        count=count,
    )

    samples: list[
        VideoFrameSample
    ] = []

    for index, timestamp in enumerate(
        timestamps
    ):
        output_path = os.path.join(
            output_dir,
            f"uniform-{index:03d}.jpg",
        )

        _extract_one_frame(
            video_path=video_path,
            output_path=output_path,
            timestamp=timestamp,
            ffmpeg=ffmpeg,
        )

        with open(
            output_path,
            "rb",
        ) as handle:
            image_bytes = handle.read()

        samples.append(
            VideoFrameSample(
                index=index,
                image_bytes=image_bytes,
                timestamp_seconds=timestamp,
            )
        )

    return samples


def _extract_scene_frames(
    *,
    video_path: str,
    output_dir: str,
    ffmpeg: str,
) -> list[bytes]:
    if not settings.CONTENT_SAFETY_VIDEO_SCENE_SAMPLING_ENABLED:
        return []

    max_scene_frames = max(
        0,
        int(
            settings.CONTENT_SAFETY_VIDEO_MAX_SCENE_FRAMES
        ),
    )

    if max_scene_frames <= 0:
        return []

    width = max(
        256,
        int(
            settings.CONTENT_SAFETY_VIDEO_FRAME_WIDTH
        ),
    )

    threshold = min(
        max(
            float(
                settings.CONTENT_SAFETY_VIDEO_SCENE_THRESHOLD
            ),
            0.05,
        ),
        0.95,
    )

    pattern = os.path.join(
        output_dir,
        "scene-%03d.jpg",
    )

    filter_value = (
        f"select=gt(scene\\,{threshold:.3f}),"
        f"scale={width}:{width}:"
        "force_original_aspect_ratio=decrease"
    )

    result = _run_process(
        [
            ffmpeg,
            "-v",
            "error",
            "-i",
            video_path,
            "-vf",
            filter_value,
            "-vsync",
            "vfr",
            "-frames:v",
            str(
                max_scene_frames
            ),
            "-q:v",
            "5",
            "-y",
            pattern,
        ]
    )

    if result.returncode != 0:
        logger.info(
            "[content_safety] scene sampling skipped "
            "because FFmpeg scene extraction failed"
        )
        return []

    paths = sorted(
        [
            os.path.join(
                output_dir,
                name,
            )
            for name in os.listdir(
                output_dir
            )
            if name.startswith(
                "scene-"
            )
            and name.endswith(
                ".jpg"
            )
        ]
    )

    frames: list[bytes] = []

    for path in paths[
        :max_scene_frames
    ]:
        try:
            with open(
                path,
                "rb",
            ) as handle:
                data = handle.read()

            if data:
                frames.append(
                    data
                )

        except OSError:
            continue

    return frames


def _merge_frame_samples(
    *,
    uniform_samples: list[VideoFrameSample],
    scene_frames: list[bytes],
) -> list[VideoFrameSample]:
    max_frames = max(
        1,
        int(
            settings.CONTENT_SAFETY_VIDEO_MAX_FRAMES
        ),
    )

    seen_hashes: set[str] = set()
    merged_bytes: list[
        tuple[
            bytes,
            float | None,
        ]
    ] = []

    for sample in uniform_samples:
        frame_hash = hashlib.sha256(
            sample.image_bytes
        ).hexdigest()

        if frame_hash in seen_hashes:
            continue

        seen_hashes.add(
            frame_hash
        )

        merged_bytes.append(
            (
                sample.image_bytes,
                sample.timestamp_seconds,
            )
        )

    for image_bytes in scene_frames:
        frame_hash = hashlib.sha256(
            image_bytes
        ).hexdigest()

        if frame_hash in seen_hashes:
            continue

        seen_hashes.add(
            frame_hash
        )

        merged_bytes.append(
            (
                image_bytes,
                None,
            )
        )

        if len(
            merged_bytes
        ) >= max_frames:
            break

    return [
        VideoFrameSample(
            index=index,
            image_bytes=image_bytes,
            timestamp_seconds=timestamp,
        )
        for index, (
            image_bytes,
            timestamp,
        ) in enumerate(
            merged_bytes[
                :max_frames
            ]
        )
    ]


def _extract_video_frames(
    *,
    video_path: str,
    probe: VideoProbe,
    work_dir: str,
    ffmpeg: str,
) -> list[VideoFrameSample]:
    frame_dir = os.path.join(
        work_dir,
        "frames",
    )

    os.makedirs(
        frame_dir,
        exist_ok=True,
    )

    uniform = _extract_uniform_frames(
        video_path=video_path,
        duration_seconds=probe.duration_seconds,
        output_dir=frame_dir,
        ffmpeg=ffmpeg,
    )

    scene_frames = _extract_scene_frames(
        video_path=video_path,
        output_dir=frame_dir,
        ffmpeg=ffmpeg,
    )

    samples = _merge_frame_samples(
        uniform_samples=uniform,
        scene_frames=scene_frames,
    )

    if not samples:
        raise ValueError(
            "No video frames could be inspected."
        )

    return samples


def _screen_one_frame(
    *,
    frame: VideoFrameSample,
    context: str,
) -> VideoFrameScreening:
    close_old_connections()

    try:
        result = check_image_safety(
            image_bytes=frame.image_bytes,
            mime_type="image/jpeg",
            context=context,
            actor=None,
            field_name="video_frame",
            run_guard=False,
            resolve_adjudication=False,
            record_event=False,
        )

        return VideoFrameScreening(
            frame=frame,
            decision=result.decision,
            risk_level=result.risk_level,
            reason_code=result.reason_code,
            provider_flagged=(
                result.provider_flagged
            ),
        )

    finally:
        close_old_connections()


def _screen_video_frames(
    *,
    frames: list[VideoFrameSample],
    context: str,
) -> list[VideoFrameScreening]:
    concurrency = max(
        1,
        min(
            int(
                settings.CONTENT_SAFETY_VIDEO_FRAME_CONCURRENCY
            ),
            len(
                frames
            ),
        ),
    )

    if concurrency == 1:
        return [
            _screen_one_frame(
                frame=frame,
                context=context,
            )
            for frame in frames
        ]

    results_by_index: dict[
        int,
        VideoFrameScreening,
    ] = {}

    with ThreadPoolExecutor(
        max_workers=concurrency
    ) as executor:
        futures = {
            executor.submit(
                _screen_one_frame,
                frame=frame,
                context=context,
            ): frame.index
            for frame in frames
        }

        for future in as_completed(
            futures
        ):
            result = future.result()

            results_by_index[
                result.frame.index
            ] = result

    return [
        results_by_index[
            frame.index
        ]
        for frame in frames
    ]


def _highest_risk(
    values: list[str],
) -> str:
    if not values:
        return SafetyRiskLevel.LOW

    return max(
        values,
        key=lambda value: (
            _RISK_ORDER.get(
                value,
                0,
            )
        ),
    )


def _select_final_visual_frames(
    *,
    frames: list[VideoFrameSample],
    preferred_indices: list[int],
) -> list[VideoFrameSample]:
    max_frames = max(
        1,
        int(
            settings.CONTENT_SAFETY_VIDEO_MAX_FINAL_VISUAL_FRAMES
        ),
    )

    frame_by_index = {
        frame.index: frame
        for frame in frames
    }

    selected: list[
        VideoFrameSample
    ] = []

    for index in preferred_indices:
        frame = frame_by_index.get(
            index
        )

        if frame is None:
            continue

        if frame in selected:
            continue

        selected.append(
            frame
        )

        if len(
            selected
        ) >= max_frames:
            return selected

    if selected:
        return selected

    if len(
        frames
    ) <= max_frames:
        return frames

    step = (
        len(
            frames
        )
        - 1
    ) / (
        max_frames - 1
    ) if max_frames > 1 else 0

    indices = {
        int(
            round(
                step * index
            )
        )
        for index in range(
            max_frames
        )
    }

    return [
        frame
        for index, frame in enumerate(
            frames
        )
        if index in indices
    ][
        :max_frames
    ]


def _evaluate_visual_safety(
    *,
    frames: list[VideoFrameSample],
    context: str,
) -> dict:
    screenings = _screen_video_frames(
        frames=frames,
        context=context,
    )

    provider_suspicious = [
        screening
        for screening in screenings
        if screening.decision
        != SafetyDecision.ALLOW
    ]

    provider_flagged = any(
        screening.provider_flagged
        for screening in screenings
    )

    provider_reason_codes = [
        screening.reason_code
        for screening in provider_suspicious
        if screening.reason_code
    ]

    preferred_indices = [
        screening.frame.index
        for screening in provider_suspicious
    ]

    guarded = False
    guard_model = ""
    guard_reason = ""

    needs_final = bool(
        provider_suspicious
    )

    if not needs_final:
        guarded = True

        frame_data_urls = [
            (
                frame.index,
                _jpeg_data_url(
                    frame.image_bytes
                ),
            )
            for frame in frames
        ]

        try:
            guard = inspect_video_visual_guard(
                frame_data_urls=frame_data_urls,
                context=context,
            )

            guard_model = guard[
                "model"
            ]

            guard_reason = guard[
                "reason_code"
            ]

            if guard[
                "decision"
            ] == SafetyDecision.REVIEW:
                needs_final = True

                preferred_indices = list(
                    guard.get(
                        "suspicious_frame_indices"
                    )
                    or []
                )

        except Exception:
            logger.exception(
                "[content_safety] video visual guard failed "
                "context=%s",
                context,
            )

            needs_final = True
            guard_reason = (
                SafetyReason.ADJUDICATION_REQUIRED
            )

    if not needs_final:
        return {
            "decision": SafetyDecision.ALLOW,
            "risk_level": SafetyRiskLevel.LOW,
            "reason_code": SafetyReason.SAFE,
            "provider_flagged": provider_flagged,
            "guarded": guarded,
            "guard_model": guard_model,
            "adjudicated": False,
            "adjudication_model": "",
        }

    if not settings.CONTENT_SAFETY_ADJUDICATION_ENABLED:
        return {
            "decision": SafetyDecision.REVIEW,
            "risk_level": SafetyRiskLevel.MEDIUM,
            "reason_code": (
                SafetyReason.ADJUDICATION_REQUIRED
            ),
            "provider_flagged": provider_flagged,
            "guarded": guarded,
            "guard_model": guard_model,
            "adjudicated": False,
            "adjudication_model": "",
        }

    selected_frames = _select_final_visual_frames(
        frames=frames,
        preferred_indices=preferred_indices,
    )

    frame_data_urls = [
        (
            frame.index,
            _jpeg_data_url(
                frame.image_bytes
            ),
        )
        for frame in selected_frames
    ]

    try:
        adjudication = adjudicate_video_visual(
            frame_data_urls=frame_data_urls,
            context=context,
            provider_reason_codes=provider_reason_codes,
            guard_reason_code=guard_reason,
        )

    except Exception:
        logger.exception(
            "[content_safety] video visual adjudication failed "
            "context=%s",
            context,
        )

        return {
            "decision": SafetyDecision.REVIEW,
            "risk_level": SafetyRiskLevel.MEDIUM,
            "reason_code": (
                SafetyReason.ADJUDICATION_REQUIRED
            ),
            "provider_flagged": provider_flagged,
            "guarded": guarded,
            "guard_model": guard_model,
            "adjudicated": False,
            "adjudication_model": "",
        }

    return {
        "decision": adjudication[
            "decision"
        ],
        "risk_level": adjudication[
            "risk_level"
        ],
        "reason_code": adjudication[
            "reason_code"
        ],
        "provider_flagged": provider_flagged,
        "guarded": guarded,
        "guard_model": guard_model,
        "adjudicated": True,
        "adjudication_model": adjudication[
            "model"
        ],
    }


def _extract_audio(
    *,
    video_path: str,
    output_path: str,
    ffmpeg: str,
) -> None:
    result = _run_process(
        [
            ffmpeg,
            "-v",
            "error",
            "-i",
            video_path,
            "-vn",
            "-map",
            "0:a:0",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "aac",
            "-b:a",
            str(
                settings.CONTENT_SAFETY_VIDEO_AUDIO_BITRATE
            ),
            "-y",
            output_path,
        ]
    )

    if (
        result.returncode != 0
        or not os.path.isfile(
            output_path
        )
        or os.path.getsize(
            output_path
        ) <= 0
    ):
        raise ValueError(
            "Video audio could not be extracted."
        )


def _text_context_for_media(
    context: str,
) -> str:
    mapping = {
        str(
            SafetyContext.MOMENT_MEDIA
        ): str(
            SafetyContext.MOMENT_CAPTION
        ),
        str(
            SafetyContext.PRAYER_MEDIA
        ): str(
            SafetyContext.PRAYER
        ),
        str(
            SafetyContext.TESTIMONY_MEDIA
        ): str(
            SafetyContext.TESTIMONY
        ),
        str(
            SafetyContext.JOURNEY_MEDIA
        ): str(
            SafetyContext.JOURNEY_TEXT
        ),
        str(
            SafetyContext.PROFILE_MEDIA
        ): str(
            SafetyContext.PROFILE_TEXT
        ),
        str(
            SafetyContext.GROUP_MESSAGE_MEDIA
        ): str(
            SafetyContext.GROUP_MESSAGE
        ),
    }

    return mapping.get(
        str(
            context
        ),
        str(
            SafetyContext.GENERIC
        ),
    )


def _split_transcript(
    text: str,
) -> list[str]:
    normalized = normalize_text_for_safety(
        text
    )

    if not normalized:
        return []

    safety_max = max(
        1000,
        int(
            settings.CONTENT_SAFETY_MAX_TEXT_CHARS
        ),
    )

    target = min(
        12_000,
        safety_max,
    )

    overlap = min(
        300,
        max(
            100,
            target // 20,
        ),
    )

    if len(
        normalized
    ) <= target:
        return [
            normalized
        ]

    chunks: list[str] = []

    start = 0
    text_length = len(
        normalized
    )

    while start < text_length:
        end = min(
            start + target,
            text_length,
        )

        if end < text_length:
            search_start = max(
                start,
                end - 700,
            )

            boundary = max(
                normalized.rfind(
                    "\n",
                    search_start,
                    end,
                ),
                normalized.rfind(
                    ". ",
                    search_start,
                    end,
                ),
                normalized.rfind(
                    " ",
                    search_start,
                    end,
                ),
            )

            if boundary > start:
                end = boundary + 1

        chunk = normalized[
            start:end
        ].strip()

        if chunk:
            chunks.append(
                chunk
            )

        if end >= text_length:
            break

        next_start = max(
            start + 1,
            end - overlap,
        )

        start = next_start

    return chunks


def _evaluate_transcript_safety(
    *,
    transcript: str,
    media_context: str,
) -> TranscriptSafety:
    normalized = normalize_text_for_safety(
        transcript
    )

    transcript_hash = hash_safety_input(
        normalized
    )

    if not normalized:
        return TranscriptSafety(
            decision=SafetyDecision.ALLOW,
            risk_level=SafetyRiskLevel.LOW,
            reason_code=SafetyReason.SAFE,
            input_hash=transcript_hash,
            chunk_count=0,
            adjudicated=False,
        )

    chunks = _split_transcript(
        normalized
    )

    text_context = _text_context_for_media(
        media_context
    )

    review_result = None
    any_adjudicated = False

    for chunk in chunks:
        result = check_text_safety(
            text=chunk,
            context=text_context,
            actor=None,
            field_name="video_transcript",
            record_event=False,
        )

        any_adjudicated = (
            any_adjudicated
            or result.adjudicated
        )

        if result.decision == SafetyDecision.BLOCK:
            return TranscriptSafety(
                decision=SafetyDecision.BLOCK,
                risk_level=result.risk_level,
                reason_code=result.reason_code,
                input_hash=transcript_hash,
                chunk_count=len(
                    chunks
                ),
                adjudicated=any_adjudicated,
            )

        if (
            result.decision
            == SafetyDecision.REVIEW
        ):
            if review_result is None:
                review_result = result

            elif (
                _RISK_ORDER.get(
                    result.risk_level,
                    0,
                )
                >
                _RISK_ORDER.get(
                    review_result.risk_level,
                    0,
                )
            ):
                review_result = result

    if review_result is not None:
        return TranscriptSafety(
            decision=SafetyDecision.REVIEW,
            risk_level=review_result.risk_level,
            reason_code=review_result.reason_code,
            input_hash=transcript_hash,
            chunk_count=len(
                chunks
            ),
            adjudicated=any_adjudicated,
        )

    return TranscriptSafety(
        decision=SafetyDecision.ALLOW,
        risk_level=SafetyRiskLevel.LOW,
        reason_code=SafetyReason.SAFE,
        input_hash=transcript_hash,
        chunk_count=len(
            chunks
        ),
        adjudicated=any_adjudicated,
    )


def _video_cache_signals() -> list[str]:
    return [
        _VIDEO_RESULT_SIGNAL,
        _video_pipeline_version(),
    ]


def _get_cached_video_result(
    *,
    input_hash: str,
    context: str,
) -> VideoSafetyResult | None:
    cached = get_cached_adjudication(
        input_hash=input_hash,
        context=context,
        active_categories=[],
        local_signals=(
            _video_cache_signals()
        ),
        model=(
            _video_result_cache_model()
        ),
        policy_version=(
            _media_policy_version()
        ),
    )

    if cached is None:
        return None

    return VideoSafetyResult(
        decision=cached[
            "decision"
        ],
        risk_level=cached[
            "risk_level"
        ],
        reason_code=cached[
            "reason_code"
        ],
        input_hash=input_hash,
        cached=True,
    )


def _cache_video_result(
    *,
    result: VideoSafetyResult,
    context: str,
) -> None:
    if (
        result.reason_code
        == SafetyReason.ADJUDICATION_REQUIRED
    ):
        return

    cache_adjudication(
        input_hash=result.input_hash,
        context=context,
        active_categories=[],
        local_signals=(
            _video_cache_signals()
        ),
        model=(
            _video_result_cache_model()
        ),
        decision=result.decision,
        risk_level=result.risk_level,
        reason_code=result.reason_code,
        policy_version=(
            _media_policy_version()
        ),
    )


def _record_video_event(
    *,
    actor,
    context: str,
    field_name: str,
    result: VideoSafetyResult,
) -> None:
    if result.decision == SafetyDecision.ALLOW:
        return

    adjudicated = (
        result.visual_adjudicated
        or result.transcript_adjudicated
    )

    adjudication_model = (
        result.visual_adjudication_model
        if result.visual_adjudicated
        else (
            settings.CONTENT_SAFETY_ADJUDICATION_MODEL
            if result.transcript_adjudicated
            else ""
        )
    )

    try:
        ContentSafetyEvent.objects.create(
            actor=(
                actor
                if getattr(
                    actor,
                    "pk",
                    None,
                )
                else None
            ),
            input_type=SafetyInputType.VIDEO,
            input_hash=result.input_hash,
            context=context,
            field_name=str(
                field_name
                or ""
            )[:80],
            decision=result.decision,
            risk_level=result.risk_level,
            reason_code=result.reason_code,
            policy_version=(
                _media_policy_version()
            ),
            provider="townlit",
            provider_model=(
                _video_pipeline_version()
            ),
            provider_flagged=(
                result.visual_provider_flagged
            ),
            adjudicated=adjudicated,
            adjudication_model=(
                str(
                    adjudication_model
                    or ""
                )
            ),
        )

    except Exception:
        logger.exception(
            "[content_safety] failed to record video event "
            "context=%s input_hash=%s",
            context,
            result.input_hash[
                :12
            ],
        )


def _build_final_result(
    *,
    input_hash: str,
    probe: VideoProbe,
    frames: list[VideoFrameSample],
    visual: dict,
    transcript: TranscriptSafety | None,
    transcript_model: str,
) -> VideoSafetyResult:
    if visual[
        "decision"
    ] == SafetyDecision.BLOCK:
        decision = SafetyDecision.BLOCK
        risk_level = visual[
            "risk_level"
        ]
        reason_code = visual[
            "reason_code"
        ]

    elif visual[
        "decision"
    ] == SafetyDecision.REVIEW:
        decision = SafetyDecision.REVIEW
        risk_level = visual[
            "risk_level"
        ]
        reason_code = visual[
            "reason_code"
        ]

    elif (
        transcript is not None
        and transcript.decision
        == SafetyDecision.BLOCK
    ):
        decision = SafetyDecision.BLOCK
        risk_level = transcript.risk_level
        reason_code = transcript.reason_code

    elif (
        transcript is not None
        and transcript.decision
        == SafetyDecision.REVIEW
    ):
        decision = SafetyDecision.REVIEW
        risk_level = transcript.risk_level
        reason_code = transcript.reason_code

    else:
        decision = SafetyDecision.ALLOW
        risk_level = SafetyRiskLevel.LOW
        reason_code = SafetyReason.SAFE

    return VideoSafetyResult(
        decision=decision,
        risk_level=risk_level,
        reason_code=reason_code,
        input_hash=input_hash,
        duration_ms=max(
            1,
            int(
                round(
                    probe.duration_seconds
                    * 1000
                )
            ),
        ),
        frame_count=len(
            frames
        ),
        visual_decision=visual[
            "decision"
        ],
        visual_reason_code=visual[
            "reason_code"
        ],
        visual_provider_flagged=visual[
            "provider_flagged"
        ],
        visual_guarded=visual[
            "guarded"
        ],
        visual_guard_model=visual[
            "guard_model"
        ],
        visual_adjudicated=visual[
            "adjudicated"
        ],
        visual_adjudication_model=visual[
            "adjudication_model"
        ],
        has_audio=probe.has_audio,
        transcript_present=(
            transcript is not None
            and bool(
                transcript.input_hash
            )
            and transcript.chunk_count > 0
        ),
        transcript_hash=(
            transcript.input_hash
            if transcript is not None
            else ""
        ),
        transcript_decision=(
            transcript.decision
            if transcript is not None
            else ""
        ),
        transcript_reason_code=(
            transcript.reason_code
            if transcript is not None
            else ""
        ),
        transcript_model=transcript_model,
        transcript_chunks=(
            transcript.chunk_count
            if transcript is not None
            else 0
        ),
        transcript_adjudicated=(
            transcript.adjudicated
            if transcript is not None
            else False
        ),
        cached=False,
    )


def _check_video_path_safety(
    *,
    video_path: str,
    input_hash: str,
    context: str,
    actor=None,
    field_name: str = "",
) -> VideoSafetyResult:
    normalized_context = _normalize_context(
        context
    )

    if not settings.CONTENT_SAFETY_ENABLED:
        return VideoSafetyResult(
            decision=SafetyDecision.ALLOW,
            risk_level=SafetyRiskLevel.LOW,
            reason_code=SafetyReason.SAFE,
            input_hash=input_hash,
        )

    cached = _get_cached_video_result(
        input_hash=input_hash,
        context=normalized_context,
    )

    if cached is not None:
        _record_video_event(
            actor=actor,
            context=normalized_context,
            field_name=field_name,
            result=cached,
        )

        return cached

    try:
        ffmpeg, ffprobe = (
            _ensure_media_binaries()
        )

    except Exception as exc:
        logger.exception(
            "[content_safety] video media binaries unavailable"
        )

        raise ContentSafetyUnavailableError() from exc

    try:
        probe = _probe_video(
            path=video_path,
            ffprobe=ffprobe,
        )

        work_dir = os.path.dirname(
            video_path
        )

        frames = _extract_video_frames(
            video_path=video_path,
            probe=probe,
            work_dir=work_dir,
            ffmpeg=ffmpeg,
        )

    except RuntimeError as exc:
        logger.exception(
            "[content_safety] video media processing unavailable "
            "input_hash=%s",
            input_hash[:12],
        )

        raise ContentSafetyUnavailableError() from exc

    visual = _evaluate_visual_safety(
        frames=frames,
        context=normalized_context,
    )

    # No need to pay for transcription if visual safety already
    # guarantees that publication cannot proceed.
    if visual[
        "decision"
    ] != SafetyDecision.ALLOW:
        result = _build_final_result(
            input_hash=input_hash,
            probe=probe,
            frames=frames,
            visual=visual,
            transcript=None,
            transcript_model="",
        )

        _cache_video_result(
            result=result,
            context=normalized_context,
        )

        _record_video_event(
            actor=actor,
            context=normalized_context,
            field_name=field_name,
            result=result,
        )

        return result

    transcript_safety: (
        TranscriptSafety
        | None
    ) = None

    transcript_model = ""

    if probe.has_audio:
        audio_path = os.path.join(
            os.path.dirname(
                video_path
            ),
            "safety-audio.m4a",
        )

        try:
            _extract_audio(
                video_path=video_path,
                output_path=audio_path,
                ffmpeg=ffmpeg,
            )

        except RuntimeError as exc:
            raise ContentSafetyUnavailableError() from exc

        try:
            transcription = transcribe_video_audio(
                audio_path=audio_path
            )

        except Exception as exc:
            logger.exception(
                "[content_safety] video transcription failed "
                "input_hash=%s",
                input_hash[:12],
            )

            raise ContentSafetyUnavailableError() from exc

        transcript_model = transcription[
            "model"
        ]

        transcript_safety = (
            _evaluate_transcript_safety(
                transcript=transcription[
                    "text"
                ],
                media_context=normalized_context,
            )
        )

    result = _build_final_result(
        input_hash=input_hash,
        probe=probe,
        frames=frames,
        visual=visual,
        transcript=transcript_safety,
        transcript_model=transcript_model,
    )

    _cache_video_result(
        result=result,
        context=normalized_context,
    )

    _record_video_event(
        actor=actor,
        context=normalized_context,
        field_name=field_name,
        result=result,
    )

    return result


def check_video_safety(
    *,
    video_bytes,
    mime_type: str | None,
    context: str,
    actor=None,
    field_name: str = "",
) -> VideoSafetyResult:
    """
    Evaluate one video before publication.
    """

    if isinstance(
        video_bytes,
        bytes,
    ):
        normalized_bytes = (
            video_bytes
        )

    elif isinstance(
        video_bytes,
        bytearray,
    ):
        normalized_bytes = bytes(
            video_bytes
        )

    elif isinstance(
        video_bytes,
        memoryview,
    ):
        normalized_bytes = (
            video_bytes.tobytes()
        )

    else:
        raise TypeError(
            "video_bytes must be bytes-like."
        )

    if not normalized_bytes:
        raise ValueError(
            "Video content is empty."
        )

    if len(
        normalized_bytes
    ) > _max_video_bytes():
        raise ValueError(
            "Video exceeds the content safety inspection size limit."
        )

    normalized_mime = _normalize_video_mime_type(
        mime_type
    )

    input_hash = _hash_video_bytes(
        normalized_bytes
    )

    with tempfile.TemporaryDirectory(
        prefix="townlit-video-safety-"
    ) as directory:
        video_path = os.path.join(
            directory,
            "source"
            + _video_suffix(
                normalized_mime
            ),
        )

        with open(
            video_path,
            "wb",
        ) as handle:
            handle.write(
                normalized_bytes
            )

        return _check_video_path_safety(
            video_path=video_path,
            input_hash=input_hash,
            context=context,
            actor=actor,
            field_name=field_name,
        )


def enforce_video_safety(
    *,
    video_bytes,
    mime_type: str | None,
    context: str,
    actor=None,
    field_name: str = "",
) -> VideoSafetyResult:
    """
    Require one video to pass before publication.
    """

    result = check_video_safety(
        video_bytes=video_bytes,
        mime_type=mime_type,
        context=context,
        actor=actor,
        field_name=field_name,
    )

    if result.decision == SafetyDecision.BLOCK:
        raise ContentSafetyBlockedError(
            reason_code=result.reason_code
        )

    if result.decision == SafetyDecision.REVIEW:
        raise ContentSafetyReviewError(
            reason_code=result.reason_code
        )

    return result


def _copy_file_to_temp(
    *,
    file_obj,
    destination_path: str,
) -> str:
    if file_obj is None:
        raise ValueError(
            "Video file is required."
        )

    max_bytes = _max_video_bytes()

    known_size = getattr(
        file_obj,
        "size",
        None,
    )

    if (
        isinstance(
            known_size,
            int,
        )
        and known_size > max_bytes
    ):
        raise ValueError(
            "Video exceeds the content safety inspection size limit."
        )

    original_position = None
    opened_here = False

    digest = hashlib.sha256()
    total = 0

    try:
        try:
            original_position = file_obj.tell()
        except Exception:
            original_position = None

        if (
            getattr(
                file_obj,
                "closed",
                False,
            )
            and hasattr(
                file_obj,
                "open",
            )
        ):
            file_obj.open(
                "rb"
            )
            opened_here = True

        if hasattr(
            file_obj,
            "seek",
        ):
            file_obj.seek(
                0
            )

        with open(
            destination_path,
            "wb",
        ) as destination:
            while True:
                chunk = file_obj.read(
                    1024 * 1024
                )

                if not chunk:
                    break

                total += len(
                    chunk
                )

                if total > max_bytes:
                    raise ValueError(
                        "Video exceeds the content safety inspection size limit."
                    )

                digest.update(
                    chunk
                )

                destination.write(
                    chunk
                )

    finally:
        if opened_here:
            try:
                file_obj.close()
            except Exception:
                pass

        elif (
            original_position is not None
            and hasattr(
                file_obj,
                "seek",
            )
        ):
            try:
                file_obj.seek(
                    original_position
                )
            except Exception:
                pass

    if total <= 0:
        raise ValueError(
            "Video content is empty."
        )

    return digest.hexdigest()


def check_video_file_safety(
    *,
    file_obj,
    context: str,
    actor=None,
    field_name: str = "",
    mime_type: str | None = None,
) -> VideoSafetyResult:
    """
    Inspect one Django uploaded/stored video without loading
    the whole source video into Python memory.
    """

    resolved_mime = (
        mime_type
        or getattr(
            file_obj,
            "content_type",
            None,
        )
    )

    normalized_mime = _normalize_video_mime_type(
        resolved_mime
    )

    with tempfile.TemporaryDirectory(
        prefix="townlit-video-safety-"
    ) as directory:
        video_path = os.path.join(
            directory,
            "source"
            + _video_suffix(
                normalized_mime
            ),
        )

        input_hash = _copy_file_to_temp(
            file_obj=file_obj,
            destination_path=video_path,
        )

        return _check_video_path_safety(
            video_path=video_path,
            input_hash=input_hash,
            context=context,
            actor=actor,
            field_name=field_name,
        )


def enforce_video_file_safety(
    *,
    file_obj,
    context: str,
    actor=None,
    field_name: str = "",
    mime_type: str | None = None,
) -> VideoSafetyResult:
    """
    Require one Django uploaded/stored video to pass.
    """

    result = check_video_file_safety(
        file_obj=file_obj,
        context=context,
        actor=actor,
        field_name=field_name,
        mime_type=mime_type,
    )

    if result.decision == SafetyDecision.BLOCK:
        raise ContentSafetyBlockedError(
            reason_code=result.reason_code
        )

    if result.decision == SafetyDecision.REVIEW:
        raise ContentSafetyReviewError(
            reason_code=result.reason_code
        )

    return result