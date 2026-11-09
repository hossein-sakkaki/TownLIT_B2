# apps/subtitles/services/ensure.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-09.
# Last Update by Hossein Sakkaki on 2026-11-09.

# apps/subtitles/services/ensure.py

from __future__ import annotations

from datetime import timedelta

from django.db import transaction
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

    # Lock the unique track row to avoid duplicate work under concurrent ensure calls.
    with transaction.atomic():
        track, created = SubtitleTrack.objects.select_for_update().get_or_create(
            transcript=transcript,
            target_language=lang,
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

        if track.status == SubtitleJobStatus.DONE and track.content:
            return track

        if track.status == SubtitleJobStatus.RUNNING:
            return track

        if track.status == SubtitleJobStatus.FAILED and not force_retry_failed:
            return track

        # A fresh PENDING row is already queued. A stale one can be recovered.
        fresh_pending = (
            not created
            and track.status == SubtitleJobStatus.PENDING
            and track.updated_at
            and track.updated_at > timezone.now() - timedelta(minutes=10)
        )
        if fresh_pending:
            return track

        track.status = SubtitleJobStatus.PENDING
        track.error = ""
        track.updated_at = timezone.now()
        track.save(update_fields=["status", "error", "updated_at"])

        from apps.subtitles.tasks import generate_subtitles_task

        transaction.on_commit(
            lambda: generate_subtitles_task.delay(
                transcript_id=transcript.pk,
                target_language=lang,
                fmt=fmt_norm,
            )
        )

    return track
