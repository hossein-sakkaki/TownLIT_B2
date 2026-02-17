# apps/subtitles/services/segment_humanizer.py

from __future__ import annotations
from typing import Iterable
import logging
from django.conf import settings

from apps.subtitles.services.prompt_builder_transcript import build_transcript_humanize_prompt

logger = logging.getLogger(__name__)

 
def humanize_segments_text(*, language: str, segments: list[str]) -> list[str]:
    # Humanize segments in one batch (keeps order)
    if not segments:
        return segments

    if not getattr(settings, "SUBTITLES_HUMANIZE_SOURCE_ENABLED", True):
        return segments

    if not settings.OPENAI_API_KEY:
        return segments

    raw_text = "\n".join([f"{i+1}. {s}" for i, s in enumerate(segments)])

    # Ask model to return same count, same numbering
    messages = [
        {
            "role": "system",
            "content": (
                "You are a professional transcription editor.\n"
                "Fix ASR transcript segments with maximum fidelity.\n"
                "Rules:\n"
                "- Do NOT add new meaning.\n"
                "- Do NOT paraphrase.\n"
                "- Keep the SAME number of lines.\n"
                "- Keep numbering exactly.\n"
                "- Output ONLY the corrected numbered lines.\n"
            ),
        },
        {
            "role": "user",
            "content": (
                f"Language: {language}\n\n"
                "Segments:\n"
                f"{raw_text}\n\n"
                "Return corrected numbered lines only."
            ),
        },
    ]

    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        model = getattr(settings, "OPENAI_TRANSCRIPT_HUMANIZE_MODEL", None) or getattr(
            settings, "OPENAI_TRANSLATION_MODEL", "gpt-4o-mini"
        )

        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.1,
        )

        out = (resp.choices[0].message.content or "").strip()
        if not out:
            return segments

        # Parse "1. xxx" lines back
        lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        fixed: list[str] = []
        for ln in lines:
            # Accept "1. text" or "1) text"
            if ". " in ln:
                fixed.append(ln.split(". ", 1)[1].strip())
            elif ") " in ln:
                fixed.append(ln.split(") ", 1)[1].strip())
            else:
                # If formatting breaks, abort safely
                return segments

        # Ensure same length
        if len(fixed) != len(segments):
            return segments

        return fixed

    except Exception:
        logger.exception("[subtitles] segment humanize failed")
        return segments
