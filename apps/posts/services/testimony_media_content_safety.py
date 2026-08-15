# apps/posts/services/testimony_media_content_safety.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-14.
# Last Update by Hossein Sakkaki on 2026-08-14.

from __future__ import annotations

import logging
import os
import tempfile

from django.conf import settings
from rest_framework import serializers

from apps.content_safety.enums import (
    SafetyContext,
    SafetyReason,
)
from apps.content_safety.exceptions import (
    ContentSafetyUnavailableError,
)
from apps.content_safety.services.image import (
    enforce_image_file_safety,
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

from apps.posts.models.testimony import Testimony


logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Image safety
# -----------------------------------------------------------------------------
def enforce_testimony_image_asset_safety(
    *,
    file_obj,
    actor,
    field_name: str,
) -> None:
    """
    Inspect one newly supplied Testimony image-like asset.

    Used for:
    - video thumbnail
    - audio artwork
    - direct thumbnail update endpoint
    - direct audio-artwork update endpoint

    Content Safety exceptions intentionally propagate unchanged so the
    structured content_safety_* API contract reaches iOS.
    """

    if not file_obj:
        return

    try:
        enforce_image_file_safety(
            file_obj=file_obj,
            context=SafetyContext.TESTIMONY_MEDIA,
            actor=actor,
            field_name=field_name,
            mime_type=getattr(
                file_obj,
                "content_type",
                None,
            ),
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise serializers.ValidationError(
            {
                field_name: str(
                    exc
                )
            }
        ) from exc


# -----------------------------------------------------------------------------
# Video safety
# -----------------------------------------------------------------------------
def _enforce_testimony_video_safety(
    *,
    file_obj,
    actor,
) -> None:
    """
    Inspect a newly supplied Testimony video.

    Video Safety includes:
    - sampled visual frames
    - visual moderation / guard / adjudication
    - audio extraction
    - transcription
    - TESTIMONY contextual text safety
    """

    if not file_obj:
        return

    try:
        enforce_video_file_safety(
            file_obj=file_obj,
            context=SafetyContext.TESTIMONY_MEDIA,
            actor=actor,
            field_name="video",
            mime_type=getattr(
                file_obj,
                "content_type",
                None,
            ),
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise serializers.ValidationError(
            {
                "video": str(
                    exc
                )
            }
        ) from exc


# -----------------------------------------------------------------------------
# Audio helpers
# -----------------------------------------------------------------------------
def _audio_suffix(
    file_obj,
) -> str:
    """
    Preserve the original extension for OpenAI transcription upload.
    """

    name = str(
        getattr(
            file_obj,
            "name",
            "",
        )
        or ""
    )

    suffix = os.path.splitext(
        name
    )[1].lower()

    if suffix:
        return suffix

    content_type = str(
        getattr(
            file_obj,
            "content_type",
            "",
        )
        or ""
    ).lower()

    mapping = {
        "audio/mpeg": ".mp3",
        "audio/mp3": ".mp3",
        "audio/mp4": ".m4a",
        "audio/x-m4a": ".m4a",
        "audio/m4a": ".m4a",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/webm": ".webm",
        "audio/ogg": ".ogg",
        "audio/flac": ".flac",
    }

    return mapping.get(
        content_type,
        ".m4a",
    )


def _remember_file_position(
    file_obj,
):
    try:
        return file_obj.tell()
    except Exception:
        return None


def _restore_file_position(
    file_obj,
    position,
) -> None:
    try:
        if position is None:
            file_obj.seek(
                0
            )
        else:
            file_obj.seek(
                position
            )
    except Exception:
        pass


def _write_audio_to_temporary_file(
    *,
    file_obj,
) -> str:
    """
    Materialize uploaded audio only into the local temp filesystem.

    Nothing is written to TownLIT's persistent storage.
    """

    suffix = _audio_suffix(
        file_obj
    )

    original_position = _remember_file_position(
        file_obj
    )

    try:
        try:
            file_obj.seek(
                0
            )
        except Exception:
            pass

        with tempfile.NamedTemporaryFile(
            prefix="townlit-testimony-audio-safety-",
            suffix=suffix,
            delete=False,
        ) as temp_file:
            if hasattr(
                file_obj,
                "chunks",
            ):
                for chunk in file_obj.chunks():
                    temp_file.write(
                        chunk
                    )

            else:
                while True:
                    chunk = file_obj.read(
                        1024 * 1024
                    )

                    if not chunk:
                        break

                    temp_file.write(
                        chunk
                    )

            return temp_file.name

    finally:
        _restore_file_position(
            file_obj,
            original_position,
        )


def _normalized_transcript(
    value,
) -> str:
    return str(
        value
        or ""
    ).strip()


def _transcript_chunks(
    transcript: str,
) -> list[str]:
    """
    Split long Audio Testimony transcripts into Text Safety sized chunks.

    This mirrors the intent of Video Safety transcript handling while keeping
    Audio Testimony independent from private video internals.
    """

    text = transcript.strip()

    if not text:
        return []

    configured_max = int(
        getattr(
            settings,
            "CONTENT_SAFETY_MAX_TEXT_CHARS",
            20000,
        )
        or 20000
    )

    chunk_size = max(
        1000,
        min(
            configured_max,
            12000,
        ),
    )

    overlap = min(
        300,
        max(
            0,
            chunk_size // 10,
        ),
    )

    if len(
        text
    ) <= chunk_size:
        return [
            text
        ]

    chunks = []
    start = 0
    text_length = len(
        text
    )

    while start < text_length:
        hard_end = min(
            start + chunk_size,
            text_length,
        )

        end = hard_end

        if hard_end < text_length:
            search_start = max(
                start,
                hard_end - 1000,
            )

            candidate = text[
                search_start:hard_end
            ]

            relative_break = max(
                candidate.rfind(
                    "\n"
                ),
                candidate.rfind(
                    ". "
                ),
                candidate.rfind(
                    "! "
                ),
                candidate.rfind(
                    "? "
                ),
                candidate.rfind(
                    " "
                ),
            )

            if relative_break > 0:
                end = (
                    search_start
                    + relative_break
                    + 1
                )

        chunk = text[
            start:end
        ].strip()

        if chunk:
            chunks.append(
                chunk
            )

        if end >= text_length:
            break

        next_start = max(
            0,
            end - overlap,
        )

        if next_start <= start:
            next_start = end

        start = next_start

    return chunks


# -----------------------------------------------------------------------------
# Audio Testimony safety
# -----------------------------------------------------------------------------
def _enforce_testimony_audio_safety(
    *,
    file_obj,
    actor,
) -> None:
    """
    Inspect spoken content in a newly supplied Audio Testimony.

    Pipeline:
    audio upload
    -> temporary file
    -> transcription
    -> TESTIMONY text safety

    Raw audio and raw transcript are not persisted by this service.
    """

    if not file_obj:
        return

    temporary_path = None

    try:
        temporary_path = _write_audio_to_temporary_file(
            file_obj=file_obj,
        )

        try:
            transcription = transcribe_video_audio(
                audio_path=temporary_path
            )

        except Exception as exc:
            logger.warning(
                "[TestimonyAudioSafety] transcription unavailable",
                exc_info=True,
            )

            raise ContentSafetyUnavailableError(
                reason_code=SafetyReason.PROVIDER_UNAVAILABLE
            ) from exc

        transcript = _normalized_transcript(
            transcription.get(
                "text"
            )
            if isinstance(
                transcription,
                dict,
            )
            else getattr(
                transcription,
                "text",
                "",
            )
        )

        # No intelligible speech was detected.
        #
        # This does not create a bypass for spoken harmful content: when speech
        # is present, the transcription model returns text and every chunk is
        # sent through authoritative TESTIMONY Text Safety.
        if not transcript:
            return

        chunks = _transcript_chunks(
            transcript
        )

        for index, chunk in enumerate(
            chunks
        ):
            enforce_text_safety(
                text=chunk,
                context=SafetyContext.TESTIMONY,
                actor=actor,
                field_name=(
                    "audio_transcript"
                    if len(
                        chunks
                    ) == 1
                    else f"audio_transcript[{index}]"
                ),
            )

    finally:
        if temporary_path:
            try:
                os.remove(
                    temporary_path
                )
            except FileNotFoundError:
                pass
            except Exception:
                logger.warning(
                    "[TestimonyAudioSafety] temp cleanup failed path=%s",
                    temporary_path,
                    exc_info=True,
                )

        _restore_file_position(
            file_obj,
            0,
        )


# -----------------------------------------------------------------------------
# Public Testimony media gate
# -----------------------------------------------------------------------------
def enforce_testimony_media_content_safety(
    *,
    validated_data,
    actor,
) -> None:
    """
    Require newly supplied Testimony media to pass before persistence.

    Written:
    - no media

    Audio:
    - optional audio artwork -> Image Safety
    - audio itself -> transcription -> TESTIMONY Text Safety

    Video:
    - optional thumbnail -> Image Safety
    - video -> Video Safety

    Existing unchanged media is intentionally not reprocessed.
    """

    testimony_type = validated_data.get(
        "type"
    )

    if testimony_type == Testimony.TYPE_WRITTEN:
        return

    if testimony_type == Testimony.TYPE_AUDIO:
        audio_artwork = validated_data.get(
            "audio_artwork"
        )

        audio = validated_data.get(
            "audio"
        )

        # Cheaper image gate first.
        if audio_artwork:
            enforce_testimony_image_asset_safety(
                file_obj=audio_artwork,
                actor=actor,
                field_name="audio_artwork",
            )

        if audio:
            _enforce_testimony_audio_safety(
                file_obj=audio,
                actor=actor,
            )

        return

    if testimony_type == Testimony.TYPE_VIDEO:
        thumbnail = validated_data.get(
            "thumbnail"
        )

        video = validated_data.get(
            "video"
        )

        # Cheaper image gate first.
        if thumbnail:
            enforce_testimony_image_asset_safety(
                file_obj=thumbnail,
                actor=actor,
                field_name="thumbnail",
            )

        if video:
            _enforce_testimony_video_safety(
                file_obj=video,
                actor=actor,
            )

        return