#
#  apps/conversation/services/media_content_safety.py
#  TownLIT
#
#  Created by Hossein Sakkaki on 2026-08-14.
#  Last Update by Hossein Sakkaki on 2026-08-14.
#

from __future__ import annotations

import os
import tempfile

from django.conf import settings
from rest_framework import serializers

from apps.content_safety.enums import (
    SafetyContext,
)
from apps.content_safety.exceptions import (
    ContentSafetyUnavailableError,
)
from apps.content_safety.services.image import (
    enforce_image_file_safety,
)
from apps.content_safety.services.normalization import (
    normalize_text_for_safety,
)
from apps.content_safety.services.text import (
    enforce_text_safety,
)
from apps.content_safety.services.video import (
    enforce_video_file_safety,
)
from apps.content_safety.services.video_transcription import (
    transcribe_video_audio,
)


# ----------------------------------------------------------------------
# Audio helpers
# ----------------------------------------------------------------------

_AUDIO_MIME_SUFFIXES = {
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/aac": ".aac",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/flac": ".flac",
    "audio/x-flac": ".flac",
}


def _max_audio_bytes() -> int:
    """
    Keep standalone Messenger audio bounded before transcription.

    A dedicated audio limit may be configured later. Until then,
    reuse the existing media safety video byte ceiling.
    """

    configured = getattr(
        settings,
        "CONTENT_SAFETY_MAX_AUDIO_BYTES",
        None,
    )

    if configured is None:
        configured = (
            settings.CONTENT_SAFETY_MAX_VIDEO_BYTES
        )

    value = int(
        configured
    )

    if value <= 0:
        raise RuntimeError(
            "Content Safety audio byte limit must be positive."
        )

    return value


def _audio_suffix(
    *,
    file_obj,
    mime_type: str | None,
) -> str:
    """
    Preserve a useful extension for the transcription provider.
    """

    normalized_mime = str(
        mime_type
        or getattr(
            file_obj,
            "content_type",
            None,
        )
        or ""
    ).strip().lower()

    suffix = _AUDIO_MIME_SUFFIXES.get(
        normalized_mime
    )

    if suffix:
        return suffix

    file_name = str(
        getattr(
            file_obj,
            "name",
            "",
        )
        or ""
    ).strip()

    extension = os.path.splitext(
        file_name
    )[1].lower()

    if extension in {
        ".mp3",
        ".m4a",
        ".mp4",
        ".aac",
        ".wav",
        ".webm",
        ".ogg",
        ".flac",
    }:
        return extension

    return ".audio"


def _copy_audio_to_temp(
    *,
    file_obj,
    destination_path: str,
) -> None:
    """
    Copy uploaded/stored audio into a private temporary file.

    The original file cursor is restored whenever possible.
    """

    if file_obj is None:
        raise ValueError(
            "Audio file is required."
        )

    max_bytes = _max_audio_bytes()

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
            "Audio exceeds the content safety inspection size limit."
        )

    original_position = None
    opened_here = False
    total = 0

    try:
        try:
            original_position = (
                file_obj.tell()
            )
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
                        "Audio exceeds the content safety inspection size limit."
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
            "Audio content is empty."
        )


def _split_audio_transcript(
    text: str,
) -> list[str]:
    """
    Keep each transcript request within the same text-safety ceiling
    used by Video Safety.
    """

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

        start = max(
            start + 1,
            end - overlap,
        )

    return chunks


def _enforce_audio_file_safety(
    *,
    file_obj,
    actor,
    audit_field_name: str,
    mime_type: str | None,
) -> None:
    """
    Inspect backend-readable group audio.

    The raw audio is copied only into an OS temporary directory,
    transcribed, inspected as GROUP_MESSAGE text, and then deleted
    automatically with the temporary directory.

    Empty/non-speech audio produces no transcript and therefore no
    text-safety action.
    """

    suffix = _audio_suffix(
        file_obj=file_obj,
        mime_type=mime_type,
    )

    with tempfile.TemporaryDirectory(
        prefix=(
            "townlit-group-audio-safety-"
        )
    ) as directory:
        audio_path = os.path.join(
            directory,
            "source"
            + suffix,
        )

        _copy_audio_to_temp(
            file_obj=file_obj,
            destination_path=audio_path,
        )

        try:
            transcription = (
                transcribe_video_audio(
                    audio_path=audio_path
                )
            )

        except Exception as exc:
            raise ContentSafetyUnavailableError() from exc

        transcript = normalize_text_for_safety(
            transcription.get(
                "text",
                "",
            )
        )

        if not transcript:
            return

        chunks = _split_audio_transcript(
            transcript
        )

        for index, chunk in enumerate(
            chunks
        ):
            field_name = (
                f"{audit_field_name}_transcript"
            )

            if len(
                chunks
            ) > 1:
                field_name = (
                    f"{field_name}[{index}]"
                )

            enforce_text_safety(
                text=chunk,
                context=(
                    SafetyContext.GROUP_MESSAGE
                ),
                actor=actor,
                field_name=field_name,
            )


# ----------------------------------------------------------------------
# Shared image enforcement
# ----------------------------------------------------------------------

def enforce_group_image_content_safety(
    *,
    file_obj,
    actor,
    field_name: str = "group_image",
    validation_field_name: str = "group_image",
    mime_type: str | None = None,
) -> None:
    """
    Require a backend-readable group image to pass before persistence.

    Used for:
    - group avatar during group creation
    - group avatar updates

    Content Safety exceptions intentionally propagate unchanged.
    Invalid media-shape errors become normal DRF validation errors.
    """

    if not file_obj:
        return

    try:
        enforce_image_file_safety(
            file_obj=file_obj,
            context=(
                SafetyContext.GROUP_MESSAGE_MEDIA
            ),
            actor=actor,
            field_name=field_name,
            mime_type=(
                mime_type
                or getattr(
                    file_obj,
                    "content_type",
                    None,
                )
            ),
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise serializers.ValidationError(
            {
                validation_field_name: str(
                    exc
                )
            }
        ) from exc


# ----------------------------------------------------------------------
# Group message media enforcement
# ----------------------------------------------------------------------

def enforce_group_message_media_content_safety(
    *,
    dialogue,
    file_obj,
    media_field_name: str,
    actor,
    audit_field_name: str | None = None,
    validation_field_name: str = "file",
    mime_type: str | None = None,
) -> None:
    """
    Require backend-readable Group Messenger media to pass.

    Important privacy boundary:
    - Group media: backend-readable -> inspect.
    - Private DM E2EE media: never inspect here.

    Supported semantic media:
    - image
    - video
    - audio transcript

    Generic files such as PDF/ZIP continue through the existing
    security and MIME validation pipeline. No document semantic
    classifier currently exists in Content Safety Core.
    """

    if dialogue is None:
        return

    if not getattr(
        dialogue,
        "is_group",
        False,
    ):
        return

    if not file_obj:
        return

    normalized_field = str(
        media_field_name
        or ""
    ).strip().lower()

    audit_name = (
        str(
            audit_field_name
            or normalized_field
        ).strip()
        or normalized_field
    )

    resolved_mime_type = (
        mime_type
        or getattr(
            file_obj,
            "content_type",
            None,
        )
    )

    try:
        if normalized_field == "image":
            enforce_image_file_safety(
                file_obj=file_obj,
                context=(
                    SafetyContext
                    .GROUP_MESSAGE_MEDIA
                ),
                actor=actor,
                field_name=audit_name,
                mime_type=resolved_mime_type,
            )

            return

        if normalized_field == "video":
            enforce_video_file_safety(
                file_obj=file_obj,
                context=(
                    SafetyContext
                    .GROUP_MESSAGE_MEDIA
                ),
                actor=actor,
                field_name=audit_name,
                mime_type=resolved_mime_type,
            )

            return

        if normalized_field == "audio":
            _enforce_audio_file_safety(
                file_obj=file_obj,
                actor=actor,
                audit_field_name=(
                    audit_name
                ),
                mime_type=(
                    resolved_mime_type
                ),
            )

            return

        
        # Generic file attachments intentionally remain outside the
        # semantic media safety core until a document-content scanner
        # is introduced.
        
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise serializers.ValidationError(
            {
                validation_field_name: str(
                    exc
                )
            }
        ) from exc