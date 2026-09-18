# apps/audio_catalog/services/lyrics_processing.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-16.
# Last Update by Hossein Sakkaki on 2026-09-18.

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable, Sequence

from django.db import transaction
from django.utils import timezone

from apps.audio_catalog.models.lyrics import MusicLyrics, MusicLyricsLine
from apps.audio_catalog.models.lyrics_word import MusicLyricsWord
from apps.audio_catalog.models.variant import MusicTrackVariant
from apps.audio_catalog.services.lyrics_alignment import (
    LyricsAlignmentError,
    LyricsForcedAlignmentResult,
    assemble_forced_alignment,
    build_forced_alignment_plan,
)
from apps.audio_catalog.services.lyrics_forced_aligner import (
    LyricsForcedAlignerDependencyError,
    LyricsForcedAlignerError,
    force_align_block,
)
from apps.subtitles.services.audio_source import fetch_audio_from_storage
from apps.subtitles.services.stt_openai import transcribe_audio


ALIGNMENT_PROVIDER = "ctc_segmentation"
ALIGNMENT_GATE_VERSION = "music-word-sync-v2"
ALIGNMENT_STRATEGY = "adaptive_blocks"
ALIGNMENT_STRATEGY_VERSION = "adaptive-block-v2"

MUSIC_LYRICS_STT_PROMPT_MAX_WORDS = 120
MUSIC_LYRICS_STT_TEMPERATURE = 0.0

DEFAULT_ALIGNMENT_MAX_BLOCK_SECONDS = 30.0
DEFAULT_ALIGNMENT_FALLBACK_BLOCK_SECONDS = (20.0, 15.0)
DEFAULT_ALIGNMENT_BLOCK_PADDING_SECONDS = 1.5

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


@dataclass(frozen=True, slots=True)
class MusicLyricsAlignmentAttempt:
    max_block_ms: int
    block_count: int
    direct_match_count: int
    text_match_ratio: float
    result: LyricsForcedAlignmentResult | None = None
    error: str = ""

    @property
    def is_persistable(self) -> bool:
        return bool(
            self.result
            and self.result.is_integrity_acceptable
        )

    @property
    def is_strong_quality(self) -> bool:
        return bool(
            self.result
            and self.result.is_acceptable
        )

    @property
    def review_recommended(self) -> bool:
        return bool(
            self.result
            and self.result.review_recommended
        )


@dataclass(frozen=True, slots=True)
class MusicLyricsAdaptiveAlignmentEvaluation:
    attempts: tuple[MusicLyricsAlignmentAttempt, ...]
    selected_attempt_index: int | None
    selection_reason: str = ""

    @property
    def selected_attempt(self) -> MusicLyricsAlignmentAttempt | None:
        if self.selected_attempt_index is None:
            return None
        return self.attempts[self.selected_attempt_index]

    @property
    def selected_result(self) -> LyricsForcedAlignmentResult | None:
        attempt = self.selected_attempt
        return attempt.result if attempt else None

    @property
    def selected_max_block_ms(self) -> int | None:
        attempt = self.selected_attempt
        return attempt.max_block_ms if attempt else None

    @property
    def is_acceptable(self) -> bool:
        """Whether one integrity-safe result can be persisted."""

        attempt = self.selected_attempt
        return bool(attempt and attempt.is_persistable)

    @property
    def review_recommended(self) -> bool:
        attempt = self.selected_attempt
        return bool(attempt and attempt.review_recommended)

    @property
    def best_attempt(self) -> MusicLyricsAlignmentAttempt | None:
        completed = [
            attempt
            for attempt in self.attempts
            if attempt.result is not None
        ]

        if not completed:
            return None

        return max(
            completed,
            key=lambda attempt: _attempt_rank(attempt.result),
        )


def build_music_lyrics_stt_prompt(canonical_text: str) -> str:
    """
    Build bounded canonical context for rough music STT anchors.

    This prompt guides transcription only. Canonical matching and hard
    timing-integrity checks remain authoritative. Acoustic confidence is
    retained as a review signal for sung music.
    """

    words = str(canonical_text or "").split()
    return " ".join(words[:MUSIC_LYRICS_STT_PROMPT_MAX_WORDS]).strip()


def configured_alignment_block_sizes_ms() -> tuple[int, ...]:
    primary_seconds = _positive_seconds_from_env(
        "LYRICS_ALIGNMENT_MAX_BLOCK_SECONDS",
        DEFAULT_ALIGNMENT_MAX_BLOCK_SECONDS,
    )

    fallback_raw = os.environ.get(
        "LYRICS_ALIGNMENT_FALLBACK_BLOCK_SECONDS",
        ",".join(str(value) for value in DEFAULT_ALIGNMENT_FALLBACK_BLOCK_SECONDS),
    ).strip()

    fallback_seconds: list[float] = []

    if fallback_raw:
        for raw_value in fallback_raw.split(","):
            value = raw_value.strip()
            if not value:
                continue

            try:
                seconds = float(value)
            except ValueError as exc:
                raise LyricsAlignmentProcessingError(
                    "LYRICS_ALIGNMENT_FALLBACK_BLOCK_SECONDS must contain "
                    "comma-separated positive numbers."
                ) from exc

            if seconds <= 0:
                raise LyricsAlignmentProcessingError(
                    "LYRICS_ALIGNMENT_FALLBACK_BLOCK_SECONDS values must be positive."
                )

            fallback_seconds.append(seconds)

    ordered_seconds = [primary_seconds]
    ordered_seconds.extend(
        value
        for value in fallback_seconds
        if value < primary_seconds
    )

    block_sizes_ms: list[int] = []

    for seconds in ordered_seconds:
        milliseconds = int(round(seconds * 1000))
        if milliseconds <= 0 or milliseconds in block_sizes_ms:
            continue
        block_sizes_ms.append(milliseconds)

    if not block_sizes_ms:
        raise LyricsAlignmentProcessingError(
            "At least one lyrics alignment block size is required."
        )

    return tuple(block_sizes_ms)


def configured_alignment_padding_ms() -> int:
    seconds = _non_negative_seconds_from_env(
        "LYRICS_ALIGNMENT_BLOCK_PADDING_SECONDS",
        DEFAULT_ALIGNMENT_BLOCK_PADDING_SECONDS,
    )
    return int(round(seconds * 1000))


def evaluate_adaptive_music_lyrics_alignment(
    *,
    canonical_text: str,
    stt_segments: Iterable[dict[str, Any]],
    audio_path: str,
    track_duration_ms: int,
    block_sizes_ms: Sequence[int] | None = None,
    padding_ms: int | None = None,
) -> MusicLyricsAdaptiveAlignmentEvaluation:
    """
    Evaluate adaptive CTC block sizes without writing to the database.

    STT is intentionally performed by the caller so one transcription can be
    reused across every CTC attempt.
    """

    if track_duration_ms <= 0:
        raise LyricsAlignmentProcessingError(
            "Track duration must be positive for adaptive lyrics alignment."
        )

    selected_block_sizes = tuple(
        int(value)
        for value in (
            block_sizes_ms
            if block_sizes_ms is not None
            else configured_alignment_block_sizes_ms()
        )
    )

    if not selected_block_sizes or any(value <= 0 for value in selected_block_sizes):
        raise LyricsAlignmentProcessingError(
            "Adaptive lyrics alignment requires positive block sizes."
        )

    selected_padding_ms = (
        configured_alignment_padding_ms()
        if padding_ms is None
        else int(padding_ms)
    )

    if selected_padding_ms < 0:
        raise LyricsAlignmentProcessingError(
            "Lyrics alignment padding cannot be negative."
        )

    segment_list = list(stt_segments)
    attempts: list[MusicLyricsAlignmentAttempt] = []

    for max_block_ms in selected_block_sizes:
        plan = None

        try:
            plan = build_forced_alignment_plan(
                canonical_text=canonical_text,
                stt_segments=segment_list,
                track_duration_ms=track_duration_ms,
                max_block_ms=max_block_ms,
                padding_ms=selected_padding_ms,
            )

            timings = []

            for block in plan.blocks:
                timings.extend(
                    force_align_block(
                        audio_path=audio_path,
                        block=block,
                    )
                )

            result = assemble_forced_alignment(
                plan=plan,
                timings=timings,
                track_duration_ms=track_duration_ms,
            )

        except LyricsForcedAlignerDependencyError:
            raise

        except (LyricsAlignmentError, LyricsForcedAlignerError) as exc:
            attempts.append(
                MusicLyricsAlignmentAttempt(
                    max_block_ms=max_block_ms,
                    block_count=len(plan.blocks) if plan else 0,
                    direct_match_count=plan.direct_match_count if plan else 0,
                    text_match_ratio=plan.text_match_ratio if plan else 0.0,
                    error=_safe_attempt_error(exc),
                )
            )
            continue

        attempts.append(
            MusicLyricsAlignmentAttempt(
                max_block_ms=max_block_ms,
                block_count=len(plan.blocks),
                direct_match_count=plan.direct_match_count,
                text_match_ratio=plan.text_match_ratio,
                result=result,
            )
        )

        if result.is_acceptable:
            return MusicLyricsAdaptiveAlignmentEvaluation(
                attempts=tuple(attempts),
                selected_attempt_index=len(attempts) - 1,
                selection_reason="strong_quality",
            )

    persistable_indices = [
        index
        for index, attempt in enumerate(attempts)
        if attempt.is_persistable
    ]

    if persistable_indices:
        selected_index = max(
            persistable_indices,
            key=lambda index: _attempt_rank(
                attempts[index].result
            ),
        )

        return MusicLyricsAdaptiveAlignmentEvaluation(
            attempts=tuple(attempts),
            selected_attempt_index=selected_index,
            selection_reason="best_integrity_candidate",
        )

    return MusicLyricsAdaptiveAlignmentEvaluation(
        attempts=tuple(attempts),
        selected_attempt_index=None,
        selection_reason="no_integrity_candidate",
    )


def validate_music_lyrics_alignment_candidate(lyrics: MusicLyrics) -> None:
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
            "Automatic alignment only accepts plain lyrics documents."
        )

    if not (lyrics.plain_text or "").strip():
        raise LyricsAlignmentNotEligibleError(
            "Canonical plain lyrics text is required."
        )

    if lyrics.lines.exists():
        raise LyricsAlignmentNotEligibleError(
            "Automatic alignment will not replace existing lyrics lines."
        )


def process_music_lyrics_alignment(*, lyrics_id: int) -> MusicLyricsAlignmentOutcome:
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
            prompt=build_music_lyrics_stt_prompt(source.canonical_text),
            temperature=MUSIC_LYRICS_STT_TEMPERATURE,
        )

        segments = stt.get("segments", []) or []

        evaluation = evaluate_adaptive_music_lyrics_alignment(
            canonical_text=source.canonical_text,
            stt_segments=segments,
            audio_path=local_audio_path,
            track_duration_ms=source.variant_duration_ms,
        )

        if not evaluation.is_acceptable:
            message = _adaptive_failure_message(evaluation)
            _record_alignment_failure_diagnostics(
                source=source,
                evaluation=evaluation,
                stt_model=str(stt.get("model", "") or ""),
                error=message,
            )
            raise LyricsAlignmentQualityError(message)

        result = evaluation.selected_result

        if result is None:
            raise LyricsAlignmentProcessingError(
                "Adaptive lyrics alignment selected no result."
            )

        if (
            source.status == MusicLyrics.Status.PUBLISHED
            and result.review_recommended
        ):
            message = (
                "Automatic lyrics alignment produced an integrity-safe "
                "result, but acoustic confidence recommends review. "
                "Published plain lyrics are never replaced with a "
                "review-recommended synchronization automatically."
            )

            _record_alignment_failure_diagnostics(
                source=source,
                evaluation=evaluation,
                stt_model=str(stt.get("model", "") or ""),
                error=message,
            )

            raise LyricsAlignmentQualityError(message)

        _validate_result_for_persistence(
            result=result,
            track_duration_ms=source.track_duration_ms,
        )

        return _persist_alignment(
            source=source,
            result=result,
            evaluation=evaluation,
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
        lyrics = MusicLyrics.objects.select_for_update().get(pk=lyrics_id)

        metadata = _metadata_dict(lyrics.metadata)
        alignment = _metadata_dict(metadata.get("alignment"))
        clean_state = str(processing_state or "").strip()

        if clean_state in {"running", "retrying"}:
            alignment["state"] = "processing"
        elif clean_state == "failed" and alignment.get("state") != "needs_review":
            alignment["state"] = "failed"
        else:
            alignment.setdefault("state", "not_started")

        alignment["processing_state"] = clean_state
        alignment["last_attempt_at"] = timezone.now().isoformat()

        clean_error = str(error or "").strip()

        if clean_error:
            alignment["last_error"] = clean_error[:500]
        elif clean_state == "running":
            alignment.pop("last_error", None)

        metadata["alignment"] = alignment
        lyrics.metadata = metadata
        lyrics.save(update_fields=("metadata", "updated_at"))


def _select_alignment_variant(lyrics: MusicLyrics) -> MusicTrackVariant:
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
    track_duration_ms = int(lyrics.track.duration_ms or 0)

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
    if not result.is_integrity_acceptable:
        failures = ", ".join(result.hard_gate_failures) or "unknown"
        raise LyricsAlignmentQualityError(
            "Automatic lyrics alignment did not pass the TownLIT integrity gate: "
            f"{failures}."
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
    evaluation: MusicLyricsAdaptiveAlignmentEvaluation,
    stt_model: str,
) -> MusicLyricsAlignmentOutcome:
    lyrics = (
        MusicLyrics.objects
        .select_for_update()
        .select_related("track", "reference_variant")
        .get(pk=source.lyrics_id)
    )

    _assert_source_is_current(lyrics=lyrics, source=source)

    variant = MusicTrackVariant.objects.select_for_update().get(pk=source.variant_id)
    _assert_variant_is_current(variant=variant, source=source)

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

    MusicLyricsLine.objects.bulk_create(line_objects, batch_size=200)

    persisted_lines = {
        line.sequence: line
        for line in (
            MusicLyricsLine.objects
            .filter(lyrics=lyrics)
            .order_by("sequence", "id")
        )
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

    MusicLyricsWord.objects.bulk_create(word_objects, batch_size=500)

    metadata = _metadata_dict(lyrics.metadata)
    alignment = _metadata_dict(metadata.get("alignment"))

    provider_metadata = (
        result.words[0].provider_metadata
        if result.words and isinstance(result.words[0].provider_metadata, dict)
        else {}
    )

    alignment.update(
        {
            "state": "synchronized",
            "processing_state": "idle",
            "quality_gate_version": ALIGNMENT_GATE_VERSION,
            "strategy": ALIGNMENT_STRATEGY,
            "strategy_version": ALIGNMENT_STRATEGY_VERSION,
            "attempt_count": len(evaluation.attempts),
            "selected_max_block_ms": evaluation.selected_max_block_ms,
            "selection_reason": evaluation.selection_reason,
            "hard_gate_passed": result.is_integrity_acceptable,
            "acoustic_quality_strong": result.is_acoustic_quality_strong,
            "quality_review_recommended": result.review_recommended,
            "quality_status": (
                "review_recommended"
                if result.review_recommended
                else "strong"
            ),
            "hard_gate_failures": list(result.hard_gate_failures),
            "acoustic_quality_warnings": list(
                result.acoustic_quality_warnings
            ),
            "attempts": [
                _alignment_attempt_payload(attempt)
                for attempt in evaluation.attempts
            ],
            "provider": provider_metadata.get("provider", ALIGNMENT_PROVIDER),
            "model": provider_metadata.get("model", ""),
            "model_license": provider_metadata.get("model_license", ""),
            "stt_model": stt_model,
            "reference_variant_id": source.variant_public_id,
            "canonical_word_count": result.canonical_word_count,
            "direct_match_count": result.direct_text_match_count,
            "text_match_ratio": result.text_match_ratio,
            "mean_alignment_confidence": result.mean_alignment_confidence,
            "low_confidence_word_count": result.low_confidence_word_count,
            "low_confidence_ratio": round(result.low_confidence_ratio, 6),
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

    alignment.pop("best_max_block_ms", None)
    alignment.pop("candidate_line_count", None)
    alignment.pop("candidate_word_count", None)
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


@transaction.atomic
def _record_alignment_failure_diagnostics(
    *,
    source: _AlignmentSource,
    evaluation: MusicLyricsAdaptiveAlignmentEvaluation,
    stt_model: str,
    error: str,
) -> None:
    lyrics = (
        MusicLyrics.objects
        .select_for_update()
        .select_related("track", "reference_variant")
        .get(pk=source.lyrics_id)
    )

    _assert_source_is_current(lyrics=lyrics, source=source)

    metadata = _metadata_dict(lyrics.metadata)
    alignment = _metadata_dict(metadata.get("alignment"))
    best_attempt = evaluation.best_attempt
    best_result = best_attempt.result if best_attempt else None
    provider_metadata = (
        best_result.words[0].provider_metadata
        if (
            best_result
            and best_result.words
            and isinstance(best_result.words[0].provider_metadata, dict)
        )
        else {}
    )

    alignment.update(
        {
            "state": "needs_review",
            "processing_state": "failed",
            "quality_gate_version": ALIGNMENT_GATE_VERSION,
            "strategy": ALIGNMENT_STRATEGY,
            "strategy_version": ALIGNMENT_STRATEGY_VERSION,
            "attempt_count": len(evaluation.attempts),
            "selection_reason": evaluation.selection_reason,
            "stt_model": stt_model,
            "reference_variant_id": source.variant_public_id,
            "attempts": [
                _alignment_attempt_payload(attempt)
                for attempt in evaluation.attempts
            ],
            "last_attempt_at": timezone.now().isoformat(),
            "last_error": str(error or "")[:500],
        }
    )

    alignment.pop("selected_max_block_ms", None)
    alignment.pop("completed_at", None)

    stale_result_keys = (
        "quality_status",
        "hard_gate_passed",
        "acoustic_quality_strong",
        "quality_review_recommended",
        "hard_gate_failures",
        "acoustic_quality_warnings",
        "canonical_word_count",
        "direct_match_count",
        "text_match_ratio",
        "mean_alignment_confidence",
        "low_confidence_word_count",
        "low_confidence_ratio",
        "non_positive_duration_count",
        "out_of_bounds_count",
        "order_violation_count",
        "overlap_violation_count",
        "overlong_word_count",
        "candidate_line_count",
        "candidate_word_count",
        "best_max_block_ms",
    )

    for key in stale_result_keys:
        alignment.pop(key, None)

    if provider_metadata:
        alignment["provider"] = provider_metadata.get(
            "provider",
            ALIGNMENT_PROVIDER,
        )
        alignment["model"] = provider_metadata.get("model", "")
        alignment["model_license"] = provider_metadata.get(
            "model_license",
            "",
        )
    else:
        alignment["provider"] = ALIGNMENT_PROVIDER
        alignment.pop("model", None)
        alignment.pop("model_license", None)

    if best_attempt is not None:
        alignment["best_max_block_ms"] = best_attempt.max_block_ms

    if best_result is not None:
        alignment.update(
            {
                "canonical_word_count": best_result.canonical_word_count,
                "direct_match_count": best_result.direct_text_match_count,
                "text_match_ratio": best_result.text_match_ratio,
                "mean_alignment_confidence": best_result.mean_alignment_confidence,
                "low_confidence_word_count": best_result.low_confidence_word_count,
                "low_confidence_ratio": round(best_result.low_confidence_ratio, 6),
                "hard_gate_passed": best_result.is_integrity_acceptable,
                "acoustic_quality_strong": best_result.is_acoustic_quality_strong,
                "quality_review_recommended": best_result.review_recommended,
                "quality_status": (
                    "review_recommended"
                    if best_result.review_recommended
                    else "strong"
                    if best_result.is_integrity_acceptable
                    else "failed"
                ),
                "hard_gate_failures": list(best_result.hard_gate_failures),
                "acoustic_quality_warnings": list(
                    best_result.acoustic_quality_warnings
                ),
                "non_positive_duration_count": best_result.non_positive_duration_count,
                "out_of_bounds_count": best_result.out_of_bounds_count,
                "order_violation_count": best_result.order_violation_count,
                "overlap_violation_count": best_result.overlap_violation_count,
                "overlong_word_count": best_result.overlong_word_count,
                "candidate_line_count": len(best_result.lines),
                "candidate_word_count": len(best_result.words),
            }
        )

    metadata["alignment"] = alignment
    lyrics.metadata = metadata
    lyrics.save(update_fields=("metadata", "updated_at"))


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

    audio_name = str(getattr(variant.audio_file, "name", "") or "").strip()

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
    """Backward-compatible accessor for the primary configured block size."""

    return configured_alignment_block_sizes_ms()[0]


def _alignment_padding_ms() -> int:
    """Backward-compatible accessor for configured alignment padding."""

    return configured_alignment_padding_ms()


def _alignment_attempt_payload(
    attempt: MusicLyricsAlignmentAttempt,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "max_block_ms": attempt.max_block_ms,
        "block_count": attempt.block_count,
        "direct_match_count": attempt.direct_match_count,
        "text_match_ratio": round(attempt.text_match_ratio, 6),
        "persistable": attempt.is_persistable,
        "strong_quality": attempt.is_strong_quality,
        "review_recommended": attempt.review_recommended,
    }

    if attempt.error:
        payload["error"] = attempt.error[:500]

    result = attempt.result

    if result is not None:
        payload.update(
            {
                "mean_alignment_confidence": result.mean_alignment_confidence,
                "low_confidence_word_count": result.low_confidence_word_count,
                "low_confidence_ratio": round(result.low_confidence_ratio, 6),
                "non_positive_duration_count": result.non_positive_duration_count,
                "out_of_bounds_count": result.out_of_bounds_count,
                "order_violation_count": result.order_violation_count,
                "overlap_violation_count": result.overlap_violation_count,
                "overlong_word_count": result.overlong_word_count,
                "hard_gate_failures": list(result.hard_gate_failures),
                "acoustic_quality_warnings": list(
                    result.acoustic_quality_warnings
                ),
            }
        )

    return payload


def _adaptive_failure_message(
    evaluation: MusicLyricsAdaptiveAlignmentEvaluation,
) -> str:
    attempted = ", ".join(
        _format_block_seconds(attempt.max_block_ms)
        for attempt in evaluation.attempts
    ) or "none"

    best_attempt = evaluation.best_attempt

    if best_attempt is None or best_attempt.result is None:
        errors = [attempt.error for attempt in evaluation.attempts if attempt.error]
        detail = errors[-1] if errors else "No complete CTC result was produced."
        return (
            "Automatic lyrics alignment exhausted adaptive block attempts "
            f"({attempted}). {detail}"
        )

    result = best_attempt.result
    failures = ", ".join(result.hard_gate_failures) or "no integrity-safe result"

    return (
        "Automatic lyrics alignment exhausted adaptive block attempts "
        f"({attempted}) without an integrity-safe result. Best attempt: "
        f"{_format_block_seconds(best_attempt.max_block_ms)}, "
        f"text={result.text_match_ratio:.2%}, "
        f"mean_confidence={result.mean_alignment_confidence:.4f}, "
        f"low_confidence={result.low_confidence_ratio:.2%}. "
        f"Failed integrity gates: {failures}."
    )


def _attempt_rank(result: LyricsForcedAlignmentResult) -> tuple:
    return (
        result.is_integrity_acceptable,
        result.is_acoustic_quality_strong,
        -len(result.acoustic_quality_warnings),
        result.text_match_ratio,
        -result.low_confidence_ratio,
        result.mean_alignment_confidence,
    )


def _safe_attempt_error(exc: Exception) -> str:
    message = str(exc or "").strip()
    return (f"{type(exc).__name__}: {message}" if message else type(exc).__name__)[:500]


def _format_block_seconds(max_block_ms: int) -> str:
    seconds = max_block_ms / 1000
    return f"{seconds:g}s"


def _positive_seconds_from_env(name: str, default: float) -> float:
    raw = os.environ.get(name, str(default)).strip()

    try:
        value = float(raw)
    except ValueError as exc:
        raise LyricsAlignmentProcessingError(
            f"{name} must be a positive number."
        ) from exc

    if value <= 0:
        raise LyricsAlignmentProcessingError(
            f"{name} must be positive."
        )

    return value


def _non_negative_seconds_from_env(name: str, default: float) -> float:
    raw = os.environ.get(name, str(default)).strip()

    try:
        value = float(raw)
    except ValueError as exc:
        raise LyricsAlignmentProcessingError(
            f"{name} must be a non-negative number."
        ) from exc

    if value < 0:
        raise LyricsAlignmentProcessingError(
            f"{name} cannot be negative."
        )

    return value


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
