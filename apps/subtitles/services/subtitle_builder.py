# apps/subtitles/services/subtitle_builder.py

from __future__ import annotations

from django.utils import timezone
from django.conf import settings

from apps.translations.services.base import translate_cached
from apps.subtitles.models import SubtitleFormat, SubtitleTrack, VideoTranscript
from apps.translations.services.language_codes import normalize_language_code


def build_subtitle_track(
    *,
    transcript: VideoTranscript,
    target_language: str,
    fmt: str = SubtitleFormat.VTT,
) -> SubtitleTrack:
    """
    Build a subtitle track:
    - If source_lang == target_lang -> NO translation (use STT text as-is)
    - Else -> translate segments via translate_cached (AWS/LLM layer)
    - Render VTT/SRT and store in SubtitleTrack.content
    """

    # -------------------------------------------------
    # Normalize language inputs (AWS-safe)
    # -------------------------------------------------
    # IMPORTANT: AWS expects codes like 'en', 'fa', 'fr-CA' (NOT 'english')
    target_lang = normalize_language_code(target_language) or (target_language or "")
    source_lang = normalize_language_code(transcript.source_language) or ""

    target_lang_norm = (target_lang or "").strip()
    source_lang_norm = (source_lang or "").strip()

    # Decide "same language" (only if source exists and both are valid)
    same_lang = bool(source_lang_norm) and (source_lang_norm.lower() == target_lang_norm.lower())

    # If source language is invalid/empty, let translation layer auto-detect (when translation is needed)
    source_lang_or_none = source_lang_norm or None

    # Normalize format input
    fmt_norm = (fmt or SubtitleFormat.VTT).lower()
    if fmt_norm not in (SubtitleFormat.VTT, SubtitleFormat.SRT):
        fmt_norm = SubtitleFormat.VTT

    # -------------------------------------------------
    # Create/Load track (idempotent)
    # -------------------------------------------------
    track, _ = SubtitleTrack.objects.get_or_create(
        transcript=transcript,
        target_language=target_lang_norm,  # ✅ store normalized code in DB
        fmt=fmt_norm,
        defaults={"status": "pending"},
    )

    # Mark running
    track.status = "running"
    track.error = ""
    track.updated_at = timezone.now()
    track.save(update_fields=["status", "error", "updated_at"])

    try:
        # -------------------------------------------------
        # Build rows
        # -------------------------------------------------
        rows = []
        qs = transcript.segments.all().order_by("idx")

        for seg in qs:
            if same_lang:
                # ✅ No translation needed (en->en, fa->fa, ...)
                out_text = seg.text
            else:
                # Translate each segment (cached)
                r = translate_cached(
                    obj=seg,
                    field_name="text",
                    user=None,
                    target_language=target_lang_norm,
                    source_language=source_lang_or_none,
                )
                out_text = r["text"]

            rows.append(
                {
                    "start_ms": seg.start_ms,
                    "end_ms": seg.end_ms,
                    "text": out_text,
                }
            )

        # -------------------------------------------------
        # Render
        # -------------------------------------------------
        from apps.subtitles.services.subtitle_renderers import render_vtt, render_srt

        if fmt_norm == SubtitleFormat.SRT:
            content = render_srt(rows)
        else:
            content = render_vtt(rows)

        # -------------------------------------------------
        # Persist result + metadata
        # -------------------------------------------------
        track.content = content
        track.status = "done"

        if same_lang:
            # Source-only track (from STT text)
            track.engine = "stt"
            track.is_humanized = False
            track.llm_model = ""
            track.prompt_version = ""
        else:
            humanize_enabled = bool(getattr(settings, "TRANSLATIONS_HUMANIZE_ENABLED", False))
            track.engine = "aws+llm" if humanize_enabled else "aws"
            track.is_humanized = humanize_enabled
            track.llm_model = getattr(settings, "OPENAI_TRANSLATION_MODEL", "") if humanize_enabled else ""
            track.prompt_version = getattr(settings, "TRANSLATIONS_HUMANIZE_PROMPT_VERSION", "") if humanize_enabled else ""

        track.updated_at = timezone.now()
        track.save(
            update_fields=[
                "content",
                "status",
                "engine",
                "is_humanized",
                "llm_model",
                "prompt_version",
                "updated_at",
            ]
        )
        return track

    except Exception as exc:
        # Make failures visible in DB (helps debugging & retries)
        track.status = "failed"
        track.error = str(exc)
        track.updated_at = timezone.now()
        track.save(update_fields=["status", "error", "updated_at"])
        raise
