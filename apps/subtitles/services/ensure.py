# apps/subtitles/services/ensure.py

from __future__ import annotations

from django.utils import timezone

from apps.subtitles.models import (
    VideoTranscript,
    SubtitleTrack,
    SubtitleFormat,
    TranscriptJobStatus,
    SubtitleJobStatus,
)
from apps.translations.services.language_codes import normalize_language_code


def _norm_fmt(fmt: str | None) -> str:
    fmt_norm = (fmt or SubtitleFormat.VTT).lower()
    if fmt_norm not in (SubtitleFormat.VTT, SubtitleFormat.SRT):
        return SubtitleFormat.VTT
    return fmt_norm


def ensure_subtitle_track(
    *,
    transcript: VideoTranscript,
    target_language: str,
    fmt: str = SubtitleFormat.VTT,
    force_retry_failed: bool = False,
) -> SubtitleTrack:
    """
    Ensure a subtitle track exists.
    - If exists: return it
    - If missing: create + enqueue task
    """

    if transcript.status != TranscriptJobStatus.DONE:
        raise RuntimeError("Transcript not ready")

    lang = normalize_language_code(target_language) or (target_language or "")
    lang = (lang or "").strip()
    if not lang:
        raise ValueError("target_language is empty")

    fmt_norm = _norm_fmt(fmt)

    track, created = SubtitleTrack.objects.get_or_create(
        transcript=transcript,
        target_language=lang,  # store normalized
        fmt=fmt_norm,
        defaults={
            "status": SubtitleJobStatus.PENDING,
            "engine": "",
            "is_humanized": False,
            "llm_model": "",
            "prompt_version": "",
            "content": "",
            "error": "",
        },
    )

    # If already done, no work
    if track.status == SubtitleJobStatus.DONE and track.content:
        return track

    # If currently running, just return
    if track.status == SubtitleJobStatus.RUNNING:
        return track

    # If failed, retry only if allowed
    if track.status == SubtitleJobStatus.FAILED and not force_retry_failed and not created:
        return track

    # Mark pending + enqueue
    track.status = SubtitleJobStatus.PENDING
    track.error = ""
    track.updated_at = timezone.now()
    track.save(update_fields=["status", "error", "updated_at"])

    from apps.subtitles.tasks import generate_subtitles_task
    generate_subtitles_task.delay(
        transcript_id=transcript.id,
        target_language=lang,
        fmt=fmt_norm,
    )

    return track
