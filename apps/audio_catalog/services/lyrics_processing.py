# apps/audio_catalog/services/lyrics_processing.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-16.
# Last Update by Hossein Sakkaki on 2026-09-16.

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from apps.audio_catalog.models.lyrics import MusicLyrics, MusicLyricsLine
from apps.audio_catalog.models.lyrics_word import MusicLyricsWord
from apps.audio_catalog.models.variant import MusicTrackVariant
from apps.audio_catalog.services.lyrics_alignment import (
    LyricsForcedAlignmentResult,
    assemble_forced_alignment,
    build_forced_alignment_plan,
)
from apps.audio_catalog.services.lyrics_forced_aligner import force_align_block
from apps.subtitles.services.audio_source import fetch_audio_from_storage
from apps.subtitles.services.stt_openai import transcribe_audio


ALIGNMENT_PROVIDER = "ctc_segmentation"
ALIGNMENT_GATE_VERSION = "music-word-sync-v1"

ALLOWED_STATUSES = {
    MusicLyrics.Status.DRAFT,
    MusicLyrics.Status.REVIEW,
    MusicLyrics.Status.PUBLISHED,
}


class LyricsAlignmentProcessingError(RuntimeError):
    pass


class LyricsAlignmentNotEligibleError(LyricsAlignmentProcessingError):
    pass


class LyricsAlignmentStaleSourceError(LyricsAlignmentProcessingError):
    pass


class LyricsAlignmentQualityError(LyricsAlignmentProcessingError):
    pass


@dataclass(frozen=True, slots=True)
class MusicLyricsAlignmentOutcome:
    lyrics_id: int
    reference_variant_id: int
    line_count: int
    word_count: int
    text_match_ratio: float
    mean_alignment_confidence: float


@dataclass(frozen=True, slots=True)
class _AlignmentSource:
    lyrics_id: int
    track_id: int
    status: str
    language_code: str
    kind: str
    timing_mode: str
    canonical_text: str
    track_duration_ms: int
    original_reference_variant_id: int | None
    variant_id: int
    variant_public_id: str
    variant_audio_name: str
    variant_duration_ms: int


def validate_music_lyrics_alignment_candidate(
    lyrics: MusicLyrics,
) -> None:
    if not lyrics.pk:
        raise LyricsAlignmentNotEligibleError(
            "Lyrics document must be saved before alignment."
        )

    if lyrics.status not in ALLOWED_STATUSES:
        raise LyricsAlignmentNotEligibleError(
            f"Lyrics status {lyrics.status!r} is not eligible for automatic alignment."
        )

    if lyrics.timing_mode != MusicLyrics.TimingMode.PLAIN:
        raise LyricsAlignmentNotEligibleError(
            "Automatic alignment V1 only accepts plain lyrics documents."
        )

    if not (lyrics.plain_text or "").strip():
        raise LyricsAlignmentNotEligibleError(
            "Canonical plain lyrics text is required."
        )

    if lyrics.lines.exists():
        raise LyricsAlignmentNotEligibleError(
            "Automatic alignment V1 will not replace existing lyrics lines."
        )


def process_music_lyrics_alignment(
    *,
    lyrics_id: int,
) -> MusicLyricsAlignmentOutcome:
    lyrics = (
        MusicLyrics.objects
        .select_related("track", "reference_variant")
        .get(pk=lyrics_id)
    )

    validate_music_lyrics_alignment_candidate(lyrics)

    variant = _select_alignment_variant(lyrics)
    source = _snapshot_source(lyrics=lyrics, variant=variant)

    local_audio_path: str | None = None

    try:
        local_audio_path = fetch_audio_from_storage(variant.audio_file)

        stt = transcribe_audio(
            wav_path=local_audio_path,
            language=(
                lyrics.language_code
                or lyrics.track.language_code
                or None
            ),
        )

        segments = stt.get("segments", []) or []

        plan = build_forced_alignment_plan(
            canonical_text=source.canonical_text,
            stt_segments=segments,
            track_duration_ms=source.variant_duration_ms,
            max_block_ms=_alignment_max_block_ms(),
            padding_ms=_alignment_padding_ms(),
        )

        timings = []

        for block in plan.blocks:
            timings.extend(
                force_align_block(
                    audio_path=local_audio_path,
                    block=block,
                )
            )

        result = assemble_forced_alignment(
            plan=plan,
            timings=timings,
            track_duration_ms=source.variant_duration_ms,
        )

        _validate_result_for_persistence(
            result=result,
            track_duration_ms=source.track_duration_ms,
        )

        return _persist_alignment(
            source=source,
            result=result,
            stt_model=str(stt.get("model", "") or ""),
        )

    finally:
        if local_audio_path and os.path.exists(local_audio_path):
            try:
                os.unlink(local_audio_path)
            except OSError:
                pass


def mark_alignment_processing_state(
    *,
    lyrics_id: int,
    processing_state: str,
    error: str = "",
) -> None:
    with transaction.atomic():
        lyrics = (
            MusicLyrics.objects
            .select_for_update()
            .get(pk=lyrics_id)
        )

        metadata = _metadata_dict(lyrics.metadata)
        alignment = _metadata_dict(metadata.get("alignment"))

        alignment.setdefault("state", "not_started")
        alignment["processing_state"] = str(processing_state or "").strip()
        alignment["last_attempt_at"] = timezone.now().isoformat()

        clean_error = str(error or "").strip()

        if clean_error:
            alignment["last_error"] = clean_error[:500]
        elif processing_state == "running":
            alignment.pop("last_error", None)

        metadata["alignment"] = alignment
        lyrics.metadata = metadata
        lyrics.save(update_fields=("metadata", "updated_at"))


def _select_alignment_variant(
    lyrics: MusicLyrics,
) -> MusicTrackVariant:
    if lyrics.reference_variant_id:
        variant = lyrics.reference_variant

        if variant is None or not _variant_is_eligible(
            variant,
            track_id=lyrics.track_id,
        ):
            raise LyricsAlignmentNotEligibleError(
                "The lyrics reference variant is not eligible for playback alignment."
            )

        return variant

    variant = (
        MusicTrackVariant.objects
        .filter(
            track_id=lyrics.track_id,
            is_active=True,
            is_converted=True,
            is_streamable=True,
        )
        .exclude(audio_file="")
        .order_by("-is_default", "sort_order", "id")
        .first()
    )

    if variant is None:
        raise LyricsAlignmentNotEligibleError(
            "No eligible playback variant was found for lyrics alignment."
        )

    return variant


def _variant_is_eligible(
    variant: MusicTrackVariant,
    *,
    track_id: int,
) -> bool:
    return (
        variant.track_id == track_id
        and bool(variant.is_active)
        and bool(variant.is_converted)
        and bool(variant.is_streamable)
        and bool(getattr(variant.audio_file, "name", ""))
    )


def _snapshot_source(
    *,
    lyrics: MusicLyrics,
    variant: MusicTrackVariant,
) -> _AlignmentSource:
    canonical_text = (lyrics.plain_text or "").strip()
    audio_name = str(getattr(variant.audio_file, "name", "") or "").strip()

    variant_duration_ms = int(
        variant.duration_ms
        or lyrics.track.duration_ms
        or 0
    )

    track_duration_ms = int(
        lyrics.track.duration_ms
        or 0
    )

    if not audio_name:
        raise LyricsAlignmentNotEligibleError(
            "Alignment playback variant has no source audio."
        )

    if variant_duration_ms <= 0 or track_duration_ms <= 0:
        raise LyricsAlignmentNotEligibleError(
            "Track duration is not available for lyrics alignment."
        )

    return _AlignmentSource(
        lyrics_id=lyrics.pk,
        track_id=lyrics.track_id,
        status=lyrics.status,
        language_code=lyrics.language_code,
        kind=lyrics.kind,
        timing_mode=lyrics.timing_mode,
        canonical_text=canonical_text,
        track_duration_ms=track_duration_ms,
        original_reference_variant_id=lyrics.reference_variant_id,
        variant_id=variant.pk,
        variant_public_id=str(variant.public_id),
        variant_audio_name=audio_name,
        variant_duration_ms=variant_duration_ms,
    )


def _validate_result_for_persistence(
    *,
    result: LyricsForcedAlignmentResult,
    track_duration_ms: int,
) -> None:
    if not result.is_acceptable:
        raise LyricsAlignmentQualityError(
            "Automatic lyrics alignment did not pass the TownLIT quality gate."
        )

    if not result.lines or not result.words:
        raise LyricsAlignmentQualityError(
            "Automatic lyrics alignment produced no timed lyrics."
        )

    if len(result.words) != result.canonical_word_count:
        raise LyricsAlignmentQualityError(
            "Aligned word count does not match the canonical lyrics word count."
        )

    expected_line_index = 0
    previous_line_end: int | None = None
    total_line_words = 0

    for line in result.lines:
        if line.line_index != expected_line_index:
            raise LyricsAlignmentQualityError(
                "Aligned lyrics line sequence is not contiguous."
            )

        if line.end_ms <= line.start_ms:
            raise LyricsAlignmentQualityError(
                f"Lyrics line {line.line_index} has invalid timing."
            )

        if line.start_ms < 0 or line.end_ms > track_duration_ms:
            raise LyricsAlignmentQualityError(
                f"Lyrics line {line.line_index} exceeds the canonical track duration."
            )

        if previous_line_end is not None and line.start_ms < previous_line_end:
            raise LyricsAlignmentQualityError(
                "Aligned lyrics lines overlap."
            )

        if not line.words:
            raise LyricsAlignmentQualityError(
                f"Lyrics line {line.line_index} contains no aligned words."
            )

        previous_word_end: int | None = None

        for word in line.words:
            if not (word.text or "").strip():
                raise LyricsAlignmentQualityError(
                    "Aligned lyrics contain an empty word."
                )

            if len(word.text) > 180:
                raise LyricsAlignmentQualityError(
                    f"Lyrics word exceeds the storage limit: {word.text!r}."
                )

            if word.end_ms <= word.start_ms:
                raise LyricsAlignmentQualityError(
                    f"Lyrics word {word.text!r} has invalid timing."
                )

            if word.start_ms < line.start_ms or word.end_ms > line.end_ms:
                raise LyricsAlignmentQualityError(
                    f"Lyrics word {word.text!r} exceeds its line timing."
                )

            if previous_word_end is not None and word.start_ms < previous_word_end:
                raise LyricsAlignmentQualityError(
                    f"Lyrics word {word.text!r} overlaps the previous word."
                )

            previous_word_end = word.end_ms
            total_line_words += 1

        previous_line_end = line.end_ms
        expected_line_index += 1

    if total_line_words != len(result.words):
        raise LyricsAlignmentQualityError(
            "Aligned line word count does not match the final word timeline."
        )


@transaction.atomic
def _persist_alignment(
    *,
    source: _AlignmentSource,
    result: LyricsForcedAlignmentResult,
    stt_model: str,
) -> MusicLyricsAlignmentOutcome:
    lyrics = (
        MusicLyrics.objects
        .select_for_update()
        .select_related("track", "reference_variant")
        .get(pk=source.lyrics_id)
    )

    _assert_source_is_current(
        lyrics=lyrics,
        source=source,
    )

    variant = (
        MusicTrackVariant.objects
        .select_for_update()
        .get(pk=source.variant_id)
    )

    _assert_variant_is_current(
        variant=variant,
        source=source,
    )

    line_objects = [
        MusicLyricsLine(
            lyrics=lyrics,
            sequence=line.line_index,
            text=line.text,
            start_ms=line.start_ms,
            end_ms=line.end_ms,
            metadata={},
        )
        for line in result.lines
    ]

    MusicLyricsLine.objects.bulk_create(
        line_objects,
        batch_size=200,
    )

    persisted_lines = {
        line.sequence: line
        for line in MusicLyricsLine.objects
        .filter(lyrics=lyrics)
        .order_by("sequence", "id")
    }

    if len(persisted_lines) != len(result.lines):
        raise LyricsAlignmentProcessingError(
            "Persisted lyrics line count does not match the alignment result."
        )

    word_objects: list[MusicLyricsWord] = []

    for line in result.lines:
        persisted_line = persisted_lines.get(line.line_index)

        if persisted_line is None:
            raise LyricsAlignmentProcessingError(
                f"Persisted lyrics line {line.line_index} could not be resolved."
            )

        for sequence, word in enumerate(line.words):
            word_objects.append(
                MusicLyricsWord(
                    line=persisted_line,
                    sequence=sequence,
                    text=word.text,
                    start_ms=word.start_ms,
                    end_ms=word.end_ms,
                    confidence=_confidence_decimal(word.confidence),
                    is_inferred=False,
                    metadata=_word_metadata(word.provider_metadata),
                )
            )

    MusicLyricsWord.objects.bulk_create(
        word_objects,
        batch_size=500,
    )

    metadata = _metadata_dict(lyrics.metadata)
    alignment = _metadata_dict(metadata.get("alignment"))

    provider_metadata = (
        result.words[0].provider_metadata
        if result.words
        and isinstance(result.words[0].provider_metadata, dict)
        else {}
    )

    alignment.update(
        {
            "state": "synchronized",
            "processing_state": "idle",
            "quality_gate_version": ALIGNMENT_GATE_VERSION,
            "provider": provider_metadata.get(
                "provider",
                ALIGNMENT_PROVIDER,
            ),
            "model": provider_metadata.get("model", ""),
            "model_license": provider_metadata.get("model_license", ""),
            "stt_model": stt_model,
            "reference_variant_id": source.variant_public_id,
            "canonical_word_count": result.canonical_word_count,
            "direct_match_count": result.direct_text_match_count,
            "text_match_ratio": result.text_match_ratio,
            "mean_alignment_confidence": result.mean_alignment_confidence,
            "low_confidence_word_count": result.low_confidence_word_count,
            "non_positive_duration_count": result.non_positive_duration_count,
            "out_of_bounds_count": result.out_of_bounds_count,
            "order_violation_count": result.order_violation_count,
            "overlap_violation_count": result.overlap_violation_count,
            "overlong_word_count": result.overlong_word_count,
            "line_count": len(result.lines),
            "word_count": len(result.words),
            "completed_at": timezone.now().isoformat(),
        }
    )

    alignment.pop("last_error", None)

    metadata["alignment"] = alignment

    lyrics.reference_variant = variant
    lyrics.timing_mode = MusicLyrics.TimingMode.LINE
    lyrics.metadata = metadata

    lyrics.save(
        update_fields=(
            "reference_variant",
            "timing_mode",
            "metadata",
            "updated_at",
        )
    )

    return MusicLyricsAlignmentOutcome(
        lyrics_id=lyrics.pk,
        reference_variant_id=variant.pk,
        line_count=len(result.lines),
        word_count=len(result.words),
        text_match_ratio=result.text_match_ratio,
        mean_alignment_confidence=result.mean_alignment_confidence,
    )


def _assert_source_is_current(
    *,
    lyrics: MusicLyrics,
    source: _AlignmentSource,
) -> None:
    if lyrics.track_id != source.track_id:
        raise LyricsAlignmentStaleSourceError(
            "Lyrics track changed while automatic alignment was running."
        )

    if lyrics.status != source.status:
        raise LyricsAlignmentStaleSourceError(
            "Lyrics status changed while automatic alignment was running."
        )

    if lyrics.language_code != source.language_code or lyrics.kind != source.kind:
        raise LyricsAlignmentStaleSourceError(
            "Lyrics language or kind changed while automatic alignment was running."
        )

    if lyrics.timing_mode != MusicLyrics.TimingMode.PLAIN:
        raise LyricsAlignmentStaleSourceError(
            "Lyrics timing mode changed while automatic alignment was running."
        )

    if (lyrics.plain_text or "").strip() != source.canonical_text:
        raise LyricsAlignmentStaleSourceError(
            "Canonical lyrics text changed while automatic alignment was running."
        )

    if lyrics.reference_variant_id != source.original_reference_variant_id:
        raise LyricsAlignmentStaleSourceError(
            "Lyrics reference variant changed while automatic alignment was running."
        )

    if int(lyrics.track.duration_ms or 0) != source.track_duration_ms:
        raise LyricsAlignmentStaleSourceError(
            "Track duration changed while automatic alignment was running."
        )

    if lyrics.lines.exists():
        raise LyricsAlignmentStaleSourceError(
            "Lyrics lines were added while automatic alignment was running."
        )


def _assert_variant_is_current(
    *,
    variant: MusicTrackVariant,
    source: _AlignmentSource,
) -> None:
    if not _variant_is_eligible(variant, track_id=source.track_id):
        raise LyricsAlignmentStaleSourceError(
            "Alignment playback variant is no longer eligible."
        )

    audio_name = str(
        getattr(variant.audio_file, "name", "")
        or ""
    ).strip()

    if audio_name != source.variant_audio_name:
        raise LyricsAlignmentStaleSourceError(
            "Alignment playback audio changed while processing was running."
        )

    duration_ms = int(
        variant.duration_ms
        or source.track_duration_ms
        or 0
    )

    if duration_ms != source.variant_duration_ms:
        raise LyricsAlignmentStaleSourceError(
            "Alignment playback duration changed while processing was running."
        )


def _alignment_max_block_ms() -> int:
    seconds = float(
        os.environ.get(
            "LYRICS_ALIGNMENT_MAX_BLOCK_SECONDS",
            "30",
        )
    )

    if seconds <= 0:
        raise LyricsAlignmentProcessingError(
            "LYRICS_ALIGNMENT_MAX_BLOCK_SECONDS must be positive."
        )

    return int(round(seconds * 1000))


def _alignment_padding_ms() -> int:
    seconds = float(
        os.environ.get(
            "LYRICS_ALIGNMENT_BLOCK_PADDING_SECONDS",
            "1.5",
        )
    )

    if seconds < 0:
        raise LyricsAlignmentProcessingError(
            "LYRICS_ALIGNMENT_BLOCK_PADDING_SECONDS cannot be negative."
        )

    return int(round(seconds * 1000))


def _confidence_decimal(value: float) -> Decimal:
    bounded = max(0.0, min(1.0, float(value)))

    return Decimal(str(bounded)).quantize(
        Decimal("0.0001"),
        rounding=ROUND_HALF_UP,
    )


def _word_metadata(value: object) -> dict:
    metadata = value if isinstance(value, dict) else {}

    allowed = (
        "timing_source",
        "confidence_source",
        "block_index",
        "token_count",
        "token_confidence_min",
        "token_confidence_max",
    )

    return {
        key: metadata[key]
        for key in allowed
        if key in metadata
    }


def _metadata_dict(value: object) -> dict:
    return dict(value) if isinstance(value, dict) else {}