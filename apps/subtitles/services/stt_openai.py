# apps/subtitles/services/stt_openai.py

from __future__ import annotations

from typing import Any

from django.conf import settings
from openai import OpenAI


def transcribe_audio(
    *,
    wav_path: str,
    language: str | None = None,
) -> dict[str, Any]:
    """
    STT -> segments with timestamps.
    """
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    model = getattr(settings, "OPENAI_STT_MODEL", "whisper-1")

    with open(wav_path, "rb") as f:
        # Request verbose output (segments)
        resp = client.audio.transcriptions.create(
            model=model,
            file=f,
            response_format="verbose_json",
            language=language,  # Optional
        )

    # resp is usually a dict-like object in openai sdk
    data = dict(resp)
    return {
        "language": data.get("language", "") or "",
        "text": data.get("text", "") or "",
        "segments": data.get("segments", []) or [],
        "model": model,
    }
