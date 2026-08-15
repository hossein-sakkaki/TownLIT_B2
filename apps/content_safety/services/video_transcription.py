# apps/content_safety/services/video_transcription.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-14.
# Last Update by Hossein Sakkaki on 2026-08-14.

from __future__ import annotations

from django.conf import settings
from openai import OpenAI


def transcribe_video_audio(
    *,
    audio_path: str,
) -> dict:
    """
    Transcribe one extracted video audio stream.

    Raw transcript is returned only to the caller and is not persisted here.
    """

    if not settings.OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is missing."
        )

    model = str(
        settings.CONTENT_SAFETY_VIDEO_TRANSCRIPTION_MODEL
    ).strip()

    if not model:
        raise RuntimeError(
            "Video transcription model is missing."
        )

    client = OpenAI(
        api_key=settings.OPENAI_API_KEY,
        timeout=(
            settings.CONTENT_SAFETY_VIDEO_TRANSCRIPTION_TIMEOUT_SECONDS
        ),
        max_retries=(
            settings.CONTENT_SAFETY_OPENAI_MAX_RETRIES
        ),
    )

    with open(
        audio_path,
        "rb",
    ) as audio_file:
        response = client.audio.transcriptions.create(
            model=model,
            file=audio_file,
            response_format="json",
        )

    text = str(
        getattr(
            response,
            "text",
            "",
        )
        or ""
    ).strip()

    return {
        "text": text,
        "model": model,
    }