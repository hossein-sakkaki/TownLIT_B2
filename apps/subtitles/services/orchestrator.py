# apps/subtitles/services/orchestrator.py

from __future__ import annotations

from apps.subtitles.models import SubtitleTrack, SubtitleFormat
from apps.subtitles.constants import SUBTITLES_PREGENERATED_LANGUAGES
from apps.translations.services.language_codes import normalize_language_code


def enqueue_default_subtitles(transcript):
    """
    Canonical orchestration policy for TownLIT subtitles.

    Policy:
      1) ALWAYS generate source-language subtitles.
      2) Pre-generate a fixed, curated list of high-impact languages.
      3) Voice generation happens ONLY after subtitle is DONE (in task).
    """
    from apps.subtitles.tasks import generate_subtitles_task

    formats = [SubtitleFormat.VTT]

    source_lang = normalize_language_code(
        getattr(transcript, "source_language", "") or ""
    )

    # 1) Source language
    if source_lang:
        for fmt in formats:
            SubtitleTrack.objects.get_or_create(
                transcript=transcript,
                target_language=source_lang,
                fmt=fmt,
            )[1] and generate_subtitles_task.delay(
                transcript_id=transcript.id,
                target_language=source_lang,
                fmt=fmt,
            )

    # 2) Pre-generated languages
    for raw_lang in SUBTITLES_PREGENERATED_LANGUAGES:
        lang = normalize_language_code(raw_lang)

        if not lang or lang == source_lang:
            continue

        for fmt in formats:
            SubtitleTrack.objects.get_or_create(
                transcript=transcript,
                target_language=lang,
                fmt=fmt,
            )[1] and generate_subtitles_task.delay(
                transcript_id=transcript.id,
                target_language=lang,
                fmt=fmt,
            )
