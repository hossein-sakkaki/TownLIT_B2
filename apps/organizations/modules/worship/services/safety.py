# apps/organizations/modules/worship/services/safety.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-07.
# Last Update by Hossein Sakkaki on 2026-09-07.
#

from __future__ import annotations

import os
import tempfile
from copy import deepcopy

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.content_safety.enums import SafetyContext
from apps.content_safety.exceptions import (
    ContentSafetyUnavailableError,
)
from apps.content_safety.services.image import (
    enforce_image_file_safety,
)
from apps.content_safety.services.text import (
    enforce_text_safety,
)
from apps.content_safety.services.video_transcription import (
    transcribe_video_audio,
)


SAFETY_METADATA_KEY = "organization_music_content_safety_v1"


def _text_chunks(value: str) -> list[str]:
    text = str(value or "").strip()

    if not text:
        return []

    size = 12000
    overlap = 250

    if len(text) <= size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + size, len(text))
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = max(
            end - overlap,
            start + 1,
        )

    return chunks


def enforce_worship_music_text_safety(
    *,
    actor,
    title="",
    subtitle="",
    description="",
    credit_text="",
):
    fields = {
        "title": title,
        "subtitle": subtitle,
        "description": description,
        "credit_text": credit_text,
    }

    for field_name, value in fields.items():
        chunks = _text_chunks(value)

        for index, chunk in enumerate(chunks):
            enforce_text_safety(
                text=chunk,
                context=SafetyContext.GENERIC,
                actor=actor,
                field_name=(
                    field_name
                    if len(chunks) == 1
                    else f"{field_name}[{index}]"
                ),
            )


def enforce_worship_music_artwork_safety(
    *,
    actor,
    file_obj,
):
    if not file_obj:
        raise ValidationError({
            "image": "Artwork image is required.",
        })

    enforce_image_file_safety(
        file_obj=file_obj,
        context=SafetyContext.GENERIC,
        actor=actor,
        field_name="worship_music_artwork",
        mime_type=getattr(
            file_obj,
            "content_type",
            None,
        ),
    )


def _audio_suffix(file_obj):
    extension = os.path.splitext(
        str(getattr(file_obj, "name", "") or "")
    )[1].lower()

    if extension:
        return extension

    content_type = str(
        getattr(file_obj, "content_type", "") or ""
    ).lower()

    return {
        "audio/mpeg": ".mp3",
        "audio/mp3": ".mp3",
        "audio/mp4": ".m4a",
        "audio/x-m4a": ".m4a",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/webm": ".webm",
        "audio/ogg": ".ogg",
        "audio/flac": ".flac",
    }.get(content_type, ".mp3")


def _materialize_audio(file_obj):
    try:
        original_position = file_obj.tell()
    except Exception:
        original_position = None

    path = None

    try:
        try:
            file_obj.seek(0)
        except Exception:
            pass

        with tempfile.NamedTemporaryFile(
            prefix="townlit-worship-music-safety-",
            suffix=_audio_suffix(file_obj),
            delete=False,
        ) as output:
            path = output.name

            if hasattr(file_obj, "chunks"):
                for chunk in file_obj.chunks():
                    output.write(chunk)
            else:
                while True:
                    chunk = file_obj.read(1024 * 1024)

                    if not chunk:
                        break

                    output.write(chunk)

        return path

    finally:
        try:
            file_obj.seek(
                original_position
                if original_position is not None
                else 0
            )
        except Exception:
            pass


def enforce_worship_music_audio_safety(
    *,
    actor,
    file_obj,
    has_vocals,
):
    if not file_obj:
        raise ValidationError({
            "audio_file": "Audio file is required.",
        })

    if not has_vocals:
        return

    local_path = _materialize_audio(
        file_obj
    )

    try:
        try:
            result = transcribe_video_audio(
                audio_path=local_path
            )
        except Exception as exc:
            raise ContentSafetyUnavailableError() from exc

        transcript = str(
            (
                result.get("text")
                if isinstance(result, dict)
                else getattr(result, "text", "")
            )
            or ""
        ).strip()

        for index, chunk in enumerate(
            _text_chunks(transcript)
        ):
            enforce_text_safety(
                text=chunk,
                context=SafetyContext.GENERIC,
                actor=actor,
                field_name=(
                    "worship_music_audio_transcript"
                    if index == 0
                    else f"worship_music_audio_transcript[{index}]"
                ),
            )

    finally:
        try:
            os.remove(local_path)
        except FileNotFoundError:
            pass


def _state(contribution):
    metadata = deepcopy(
        contribution.metadata
        if isinstance(contribution.metadata, dict)
        else {}
    )

    state = metadata.get(
        SAFETY_METADATA_KEY
    )

    if not isinstance(state, dict):
        state = {}

    return metadata, state


def mark_worship_music_text_safety(
    *,
    contribution,
):
    metadata, state = _state(
        contribution
    )

    state["text_passed"] = True
    state["text_checked_at"] = (
        timezone.now().isoformat()
    )

    metadata[SAFETY_METADATA_KEY] = state
    contribution.metadata = metadata

    contribution.save(
        update_fields=[
            "metadata",
            "updated_at",
        ]
    )


def mark_worship_music_asset_safety(
    *,
    contribution,
    kind,
    public_id,
):
    if kind not in {"audio", "artwork"}:
        raise ValueError(
            "Unsupported Worship music safety asset kind."
        )

    metadata, state = _state(
        contribution
    )

    key = (
        "audio_variant_public_ids"
        if kind == "audio"
        else "artwork_public_ids"
    )

    values = {
        str(value)
        for value in state.get(key, [])
        if value
    }

    values.add(
        str(public_id)
    )

    state[key] = sorted(values)
    state[f"{kind}_checked_at"] = (
        timezone.now().isoformat()
    )

    metadata[SAFETY_METADATA_KEY] = state
    contribution.metadata = metadata

    contribution.save(
        update_fields=[
            "metadata",
            "updated_at",
        ]
    )


def assert_worship_music_safety_ready(
    *,
    contribution,
):
    metadata = (
        contribution.metadata
        if isinstance(contribution.metadata, dict)
        else {}
    )

    state = metadata.get(
        SAFETY_METADATA_KEY
    )

    if not isinstance(state, dict):
        raise ValidationError(
            "Organization music Content Safety state is missing."
        )

    if not state.get("text_passed"):
        raise ValidationError(
            "Organization music text has not passed Content Safety."
        )

    artwork = (
        contribution.track.artworks
        .filter(
            is_primary=True,
            is_active=True,
            is_converted=True,
        )
        .first()
    )

    if artwork is None:
        raise ValidationError(
            "Primary artwork is not ready."
        )

    approved_artworks = {
        str(value)
        for value in state.get(
            "artwork_public_ids",
            [],
        )
    }

    if str(artwork.public_id) not in approved_artworks:
        raise ValidationError(
            "Primary artwork has not passed Content Safety."
        )

    variant = (
        contribution.track.variants
        .filter(
            is_default=True,
            is_active=True,
            is_converted=True,
            is_streamable=True,
        )
        .first()
    )

    if variant is None:
        raise ValidationError(
            "Default playback variant is not ready."
        )

    approved_audio = {
        str(value)
        for value in state.get(
            "audio_variant_public_ids",
            [],
        )
    }

    if str(variant.public_id) not in approved_audio:
        raise ValidationError(
            "Default playback audio has not passed Content Safety."
        )