# apps/subtitles/services/stt_openai.py
# TownLIT
#
# Last Update by Hossein Sakkaki on 2026-09-18.

from __future__ import annotations

from typing import Any

from django.conf import settings
from openai import OpenAI


def transcribe_audio(
    *,
    wav_path: str,
    language: str | None = None,
    prompt: str | None = None,
    include_word_timestamps: bool = False,
    temperature: float | None = None,
) -> dict[str, Any]:
    """
    Transcribe audio through TownLIT's canonical STT provider.

    Backward compatibility:
    - Existing callers keep the original request shape.
    - Existing callers keep the original response contract.
    - Prompt, temperature, and word timestamps are opt-in only.
    """

    client = OpenAI(
        api_key=settings.OPENAI_API_KEY,
    )

    model = getattr(
        settings,
        "OPENAI_STT_MODEL",
        "whisper-1",
    )

    clean_prompt = str(prompt or "").strip()

    use_extended_request = (
        bool(clean_prompt)
        or include_word_timestamps
        or temperature is not None
    )

    with open(wav_path, "rb") as audio_file:
        if not use_extended_request:
            # Preserve the original production request exactly.
            response = client.audio.transcriptions.create(
                model=model,
                file=audio_file,
                response_format="verbose_json",
                language=language,
            )
        else:
            request_kwargs: dict[str, Any] = {
                "model": model,
                "file": audio_file,
                "response_format": "verbose_json",
                "language": language,
            }

            if clean_prompt:
                request_kwargs["prompt"] = clean_prompt

            if include_word_timestamps:
                request_kwargs["timestamp_granularities"] = [
                    "word",
                    "segment",
                ]

            if temperature is not None:
                request_kwargs["temperature"] = float(temperature)

            response = client.audio.transcriptions.create(
                **request_kwargs
            )

    # Preserve the response contract used by production callers.
    data = dict(response)

    result: dict[str, Any] = {
        "language": data.get("language", "") or "",
        "text": data.get("text", "") or "",
        "segments": data.get("segments", []) or [],
        "model": model,
    }

    if include_word_timestamps:
        result["words"] = _normalize_response_items(
            data.get("words", []) or []
        )

    return result


def _normalize_response_items(
    items: Any,
) -> list[dict[str, Any]]:
    """
    Normalize optional SDK response models for internal consumers.

    Existing subtitle segment objects are intentionally left untouched.
    """

    if not isinstance(items, (list, tuple)):
        return []

    normalized: list[dict[str, Any]] = []

    for item in items:
        if isinstance(item, dict):
            normalized.append(item)
            continue

        model_dump = getattr(
            item,
            "model_dump",
            None,
        )

        if callable(model_dump):
            value = model_dump()

            if isinstance(value, dict):
                normalized.append(value)
                continue

        try:
            value = dict(item)
        except (TypeError, ValueError):
            continue

        if isinstance(value, dict):
            normalized.append(value)

    return normalized