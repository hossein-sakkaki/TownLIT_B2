# apps/audio_catalog/services/lyrics_alignment.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-16.
# Last Update by Hossein Sakkaki on 2026-09-18.

from __future__ import annotations

import math
import re
import unicodedata

from bisect import bisect_left
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Iterable


WORD_PATTERN = re.compile(
    r"[^\W_]+(?:['’][^\W_]+)*",
    flags=re.UNICODE,
)

MIN_TEXT_MATCH_SIMILARITY = 0.72
MIN_TEXT_MATCH_RATIO = 0.80
MIN_MEAN_ALIGNMENT_CONFIDENCE = 0.20
MAX_LOW_CONFIDENCE_RATIO = 0.25

DEFAULT_MAX_BLOCK_MS = 30_000
DEFAULT_BLOCK_PADDING_MS = 1_500

LOW_CONFIDENCE_THRESHOLD = 0.25
MAX_ACCEPTABLE_WORD_DURATION_MS = 8_000
MAX_ACCEPTABLE_WORD_OVERLAP_MS = 250


class LyricsAlignmentError(
    ValueError
):
    pass


@dataclass(
    frozen=True,
    slots=True,
)
class CanonicalLyricsWord:
    global_index: int
    line_index: int
    word_index: int
    text: str
    normalized: str


@dataclass(
    frozen=True,
    slots=True,
)
class STTLyricsSegment:
    index: int
    start_ms: int
    end_ms: int
    text: str


@dataclass(
    frozen=True,
    slots=True,
)
class LyricsAlignmentBlock:
    index: int
    start_ms: int
    end_ms: int
    words: tuple[
        CanonicalLyricsWord,
        ...,
    ]

    @property
    def duration_ms(
        self,
    ) -> int:
        return (
            self.end_ms
            - self.start_ms
        )


@dataclass(
    frozen=True,
    slots=True,
)
class LyricsAlignmentPlan:
    canonical_lines: tuple[
        str,
        ...,
    ]

    canonical_words: tuple[
        CanonicalLyricsWord,
        ...,
    ]

    stt_segments: tuple[
        STTLyricsSegment,
        ...,
    ]

    blocks: tuple[
        LyricsAlignmentBlock,
        ...,
    ]

    direct_match_count: int
    text_match_ratio: float


@dataclass(
    frozen=True,
    slots=True,
)
class ForcedWordTiming:
    global_index: int
    text: str
    start_ms: int
    end_ms: int
    confidence: float
    provider_metadata: dict[str, Any]


@dataclass(
    frozen=True,
    slots=True,
)
class TimedLyricsLine:
    line_index: int
    text: str
    start_ms: int
    end_ms: int

    words: tuple[
        ForcedWordTiming,
        ...,
    ]


@dataclass(
    frozen=True,
    slots=True,
)
class LyricsForcedAlignmentResult:
    lines: tuple[
        TimedLyricsLine,
        ...,
    ]

    words: tuple[
        ForcedWordTiming,
        ...,
    ]

    canonical_word_count: int
    direct_text_match_count: int
    text_match_ratio: float

    mean_alignment_confidence: float
    low_confidence_word_count: int

    non_positive_duration_count: int
    out_of_bounds_count: int
    order_violation_count: int
    overlap_violation_count: int
    overlong_word_count: int

    @property
    def temporal_violation_count(
        self,
    ) -> int:
        return (
            self.non_positive_duration_count
            + self.out_of_bounds_count
            + self.order_violation_count
            + self.overlap_violation_count
        )

    @property
    def low_confidence_ratio(
        self,
    ) -> float:
        if not self.canonical_word_count:
            return 1.0

        return (
            self.low_confidence_word_count
            / self.canonical_word_count
        )

    @property
    def quality_gate_failures(
        self,
    ) -> tuple[str, ...]:
        failures: list[str] = []

        if self.canonical_word_count <= 0:
            failures.append(
                "canonical_word_count <= 0"
            )

        if (
            self.text_match_ratio
            < MIN_TEXT_MATCH_RATIO
        ):
            failures.append(
                "text_match_ratio < "
                f"{MIN_TEXT_MATCH_RATIO:.0%}"
            )

        if self.temporal_violation_count:
            failures.append(
                "temporal_violation_count > 0"
            )

        if self.overlong_word_count:
            failures.append(
                "overlong_word_count > 0"
            )

        if (
            self.mean_alignment_confidence
            < MIN_MEAN_ALIGNMENT_CONFIDENCE
        ):
            failures.append(
                "mean_alignment_confidence < "
                f"{MIN_MEAN_ALIGNMENT_CONFIDENCE:.2f}"
            )

        if (
            self.low_confidence_ratio
            > MAX_LOW_CONFIDENCE_RATIO
        ):
            failures.append(
                "low_confidence_ratio > "
                f"{MAX_LOW_CONFIDENCE_RATIO:.0%}"
            )

        return tuple(failures)

    @property
    def is_acceptable(
        self,
    ) -> bool:
        return not self.quality_gate_failures


@dataclass(
    frozen=True,
    slots=True,
)
class _STTToken:
    index: int
    segment_index: int
    normalized: str


def build_forced_alignment_plan(
    *,
    canonical_text: str,
    stt_segments: Iterable[
        dict[str, Any]
    ],
    track_duration_ms: int,
    max_block_ms: int = DEFAULT_MAX_BLOCK_MS,
    padding_ms: int = DEFAULT_BLOCK_PADDING_MS,
) -> LyricsAlignmentPlan:
    if track_duration_ms <= 0:
        raise LyricsAlignmentError(
            "Track duration must be positive."
        )

    if max_block_ms <= 0:
        raise LyricsAlignmentError(
            "Maximum alignment block duration must be positive."
        )

    if padding_ms < 0:
        raise LyricsAlignmentError(
            "Alignment padding must not be negative."
        )

    canonical_lines = (
        _canonical_lines(
            canonical_text
        )
    )

    canonical_words = (
        _canonical_words(
            canonical_lines
        )
    )

    if not canonical_words:
        raise LyricsAlignmentError(
            "Canonical lyrics contain no words."
        )

    parsed_segments = (
        _parse_stt_segments(
            stt_segments,
            track_duration_ms=track_duration_ms,
        )
    )

    if not parsed_segments:
        raise LyricsAlignmentError(
            "STT returned no usable segments."
        )

    stt_tokens = (
        _flatten_stt_tokens(
            parsed_segments
        )
    )

    if not stt_tokens:
        raise LyricsAlignmentError(
            "STT segments contain no usable words."
        )

    matches = _sequence_alignment(
        canonical_words,
        stt_tokens,
    )

    direct_match_count = len(
        matches
    )

    text_match_ratio = (
        direct_match_count
        / len(
            canonical_words
        )
    )

    if (
        text_match_ratio
        < MIN_TEXT_MATCH_RATIO
    ):
        raise LyricsAlignmentError(
            (
                "STT transcript does not match canonical lyrics "
                "well enough for forced alignment. "
                f"Match ratio: {text_match_ratio:.2%}."
            )
        )

    assignments = (
        _assign_canonical_words_to_segments(
            canonical_count=len(
                canonical_words
            ),
            matches=matches,
            stt_tokens=stt_tokens,
        )
    )

    blocks = _build_blocks(
        canonical_words=canonical_words,
        segments=parsed_segments,
        assignments=assignments,
        track_duration_ms=track_duration_ms,
        max_block_ms=max_block_ms,
        padding_ms=padding_ms,
    )

    if not blocks:
        raise LyricsAlignmentError(
            "Could not build forced-alignment blocks."
        )

    return LyricsAlignmentPlan(
        canonical_lines=tuple(
            canonical_lines
        ),
        canonical_words=tuple(
            canonical_words
        ),
        stt_segments=tuple(
            parsed_segments
        ),
        blocks=tuple(
            blocks
        ),
        direct_match_count=direct_match_count,
        text_match_ratio=round(
            text_match_ratio,
            6,
        ),
    )


def assemble_forced_alignment(
    *,
    plan: LyricsAlignmentPlan,
    timings: Iterable[
        ForcedWordTiming
    ],
    track_duration_ms: int,
) -> LyricsForcedAlignmentResult:
    timing_list = sorted(
        list(
            timings
        ),
        key=lambda item: item.global_index,
    )

    expected_count = len(
        plan.canonical_words
    )

    if len(
        timing_list
    ) != expected_count:
        raise LyricsAlignmentError(
            (
                "Forced aligner returned an unexpected "
                "number of words. "
                f"Expected {expected_count}, "
                f"received {len(timing_list)}."
            )
        )

    by_index: dict[
        int,
        ForcedWordTiming,
    ] = {}

    for timing in timing_list:
        if timing.global_index in by_index:
            raise LyricsAlignmentError(
                (
                    "Forced aligner returned duplicate "
                    f"word index {timing.global_index}."
                )
            )

        by_index[
            timing.global_index
        ] = timing

    ordered: list[
        ForcedWordTiming
    ] = []

    for canonical in plan.canonical_words:
        timing = by_index.get(
            canonical.global_index
        )

        if timing is None:
            raise LyricsAlignmentError(
                (
                    "Forced aligner did not return timing for "
                    f"canonical word {canonical.global_index}."
                )
            )

        if (
            _normalize_word(
                timing.text
            )
            != canonical.normalized
        ):
            raise LyricsAlignmentError(
                (
                    "Forced aligner word identity mismatch at "
                    f"index {canonical.global_index}: "
                    f"{timing.text!r} != {canonical.text!r}."
                )
            )

        ordered.append(
            timing
        )

    (
        non_positive_duration_count,
        out_of_bounds_count,
        order_violation_count,
        overlap_violation_count,
        overlong_word_count,
    ) = _temporal_health(
        ordered,
        track_duration_ms=track_duration_ms,
    )

    confidences = [
        max(
            0.0,
            min(
                1.0,
                float(
                    timing.confidence
                ),
            ),
        )
        for timing in ordered
    ]

    mean_confidence = (
        sum(
            confidences
        )
        / len(
            confidences
        )
        if confidences
        else 0.0
    )

    low_confidence_count = sum(
        1
        for confidence in confidences
        if (
            confidence
            < LOW_CONFIDENCE_THRESHOLD
        )
    )

    lines = _build_timed_lines(
        plan=plan,
        timings=ordered,
    )

    return LyricsForcedAlignmentResult(
        lines=tuple(
            lines
        ),
        words=tuple(
            ordered
        ),
        canonical_word_count=expected_count,
        direct_text_match_count=(
            plan.direct_match_count
        ),
        text_match_ratio=(
            plan.text_match_ratio
        ),
        mean_alignment_confidence=round(
            mean_confidence,
            6,
        ),
        low_confidence_word_count=(
            low_confidence_count
        ),
        non_positive_duration_count=(
            non_positive_duration_count
        ),
        out_of_bounds_count=(
            out_of_bounds_count
        ),
        order_violation_count=(
            order_violation_count
        ),
        overlap_violation_count=(
            overlap_violation_count
        ),
        overlong_word_count=(
            overlong_word_count
        ),
    )


def _canonical_lines(
    text: str,
) -> list[str]:
    return [
        line.strip()
        for line in str(
            text
            or ""
        ).splitlines()
        if line.strip()
    ]


def _canonical_words(
    lines: list[str],
) -> list[
    CanonicalLyricsWord
]:
    result: list[
        CanonicalLyricsWord
    ] = []

    global_index = 0

    for line_index, line in enumerate(
        lines
    ):
        word_index = 0

        for match in WORD_PATTERN.finditer(
            line
        ):
            raw = match.group(
                0
            )

            normalized = (
                _normalize_word(
                    raw
                )
            )

            if not normalized:
                continue

            result.append(
                CanonicalLyricsWord(
                    global_index=global_index,
                    line_index=line_index,
                    word_index=word_index,
                    text=raw,
                    normalized=normalized,
                )
            )

            global_index += 1
            word_index += 1

    return result


def _parse_stt_segments(
    values: Iterable[
        dict[str, Any]
    ],
    *,
    track_duration_ms: int,
) -> list[
    STTLyricsSegment
]:
    result: list[
        STTLyricsSegment
    ] = []

    for value in values:
        if not isinstance(
            value,
            dict,
        ):
            continue

        text = str(
            value.get(
                "text",
                "",
            )
            or ""
        ).strip()

        if not text:
            continue

        try:
            start_seconds = float(
                value.get(
                    "start"
                )
            )

            end_seconds = float(
                value.get(
                    "end"
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            continue

        if (
            not math.isfinite(
                start_seconds
            )
            or not math.isfinite(
                end_seconds
            )
        ):
            continue

        start_ms = max(
            0,
            int(
                round(
                    start_seconds
                    * 1000
                )
            ),
        )

        end_ms = min(
            track_duration_ms,
            int(
                round(
                    end_seconds
                    * 1000
                )
            ),
        )

        if end_ms <= start_ms:
            continue

        result.append(
            STTLyricsSegment(
                index=len(
                    result
                ),
                start_ms=start_ms,
                end_ms=end_ms,
                text=text,
            )
        )

    return result


def _flatten_stt_tokens(
    segments: list[
        STTLyricsSegment
    ],
) -> list[
    _STTToken
]:
    result: list[
        _STTToken
    ] = []

    for segment in segments:
        for match in WORD_PATTERN.finditer(
            segment.text
        ):
            normalized = (
                _normalize_word(
                    match.group(
                        0
                    )
                )
            )

            if not normalized:
                continue

            result.append(
                _STTToken(
                    index=len(
                        result
                    ),
                    segment_index=(
                        segment.index
                    ),
                    normalized=normalized,
                )
            )

    return result


def _sequence_alignment(
    canonical_words: list[
        CanonicalLyricsWord
    ],
    stt_tokens: list[
        _STTToken
    ],
) -> list[
    tuple[
        int,
        int,
    ]
]:
    canonical_count = len(
        canonical_words
    )

    stt_count = len(
        stt_tokens
    )

    gap_score = -0.90

    scores = [
        [
            0.0
            for _ in range(
                stt_count + 1
            )
        ]
        for _ in range(
            canonical_count + 1
        )
    ]

    moves = [
        [
            0
            for _ in range(
                stt_count + 1
            )
        ]
        for _ in range(
            canonical_count + 1
        )
    ]

    for i in range(
        1,
        canonical_count + 1,
    ):
        scores[
            i
        ][
            0
        ] = (
            scores[
                i - 1
            ][
                0
            ]
            + gap_score
        )

        moves[
            i
        ][
            0
        ] = 1

    for j in range(
        1,
        stt_count + 1,
    ):
        scores[
            0
        ][
            j
        ] = (
            scores[
                0
            ][
                j - 1
            ]
            + gap_score
        )

        moves[
            0
        ][
            j
        ] = 2

    for i in range(
        1,
        canonical_count + 1,
    ):
        canonical = (
            canonical_words[
                i - 1
            ]
        )

        for j in range(
            1,
            stt_count + 1,
        ):
            stt = (
                stt_tokens[
                    j - 1
                ]
            )

            similarity = (
                _word_similarity(
                    canonical.normalized,
                    stt.normalized,
                )
            )

            diagonal = (
                scores[
                    i - 1
                ][
                    j - 1
                ]
                + _match_score(
                    similarity
                )
            )

            delete_canonical = (
                scores[
                    i - 1
                ][
                    j
                ]
                + gap_score
            )

            skip_stt = (
                scores[
                    i
                ][
                    j - 1
                ]
                + gap_score
            )

            best = max(
                diagonal,
                delete_canonical,
                skip_stt,
            )

            scores[
                i
            ][
                j
            ] = best

            if best == diagonal:
                moves[
                    i
                ][
                    j
                ] = 0
            elif (
                best
                == delete_canonical
            ):
                moves[
                    i
                ][
                    j
                ] = 1
            else:
                moves[
                    i
                ][
                    j
                ] = 2

    pairs: list[
        tuple[
            int,
            int,
        ]
    ] = []

    i = canonical_count
    j = stt_count

    while i > 0 or j > 0:
        if i <= 0:
            j -= 1
            continue

        if j <= 0:
            i -= 1
            continue

        move = moves[
            i
        ][
            j
        ]

        if move == 0:
            similarity = (
                _word_similarity(
                    canonical_words[
                        i - 1
                    ].normalized,
                    stt_tokens[
                        j - 1
                    ].normalized,
                )
            )

            if (
                similarity
                >= MIN_TEXT_MATCH_SIMILARITY
            ):
                pairs.append(
                    (
                        i - 1,
                        j - 1,
                    )
                )

            i -= 1
            j -= 1

        elif move == 1:
            i -= 1

        else:
            j -= 1

    pairs.reverse()

    return pairs


def _assign_canonical_words_to_segments(
    *,
    canonical_count: int,
    matches: list[
        tuple[
            int,
            int,
        ]
    ],
    stt_tokens: list[
        _STTToken
    ],
) -> list[int]:
    matched_positions = [
        canonical_index
        for (
            canonical_index,
            _,
        ) in matches
    ]

    matched_segments = [
        stt_tokens[
            stt_index
        ].segment_index
        for (
            _,
            stt_index,
        ) in matches
    ]

    if not matched_positions:
        raise LyricsAlignmentError(
            "No canonical/STT text anchors were found."
        )

    exact = {
        canonical_index: segment_index
        for (
            canonical_index,
            segment_index,
        ) in zip(
            matched_positions,
            matched_segments,
        )
    }

    assignments: list[
        int
    ] = []

    for canonical_index in range(
        canonical_count
    ):
        if canonical_index in exact:
            assignments.append(
                exact[
                    canonical_index
                ]
            )
            continue

        insert_index = bisect_left(
            matched_positions,
            canonical_index,
        )

        if insert_index <= 0:
            assignments.append(
                matched_segments[
                    0
                ]
            )
            continue

        if (
            insert_index
            >= len(
                matched_positions
            )
        ):
            assignments.append(
                matched_segments[
                    -1
                ]
            )
            continue

        left_word = (
            matched_positions[
                insert_index - 1
            ]
        )

        right_word = (
            matched_positions[
                insert_index
            ]
        )

        left_segment = (
            matched_segments[
                insert_index - 1
            ]
        )

        right_segment = (
            matched_segments[
                insert_index
            ]
        )

        if (
            left_segment
            == right_segment
        ):
            assignments.append(
                left_segment
            )
            continue

        left_distance = (
            canonical_index
            - left_word
        )

        right_distance = (
            right_word
            - canonical_index
        )

        assignments.append(
            left_segment
            if (
                left_distance
                <= right_distance
            )
            else right_segment
        )

    monotonic: list[
        int
    ] = []

    previous = 0

    for index, value in enumerate(
        assignments
    ):
        if index == 0:
            previous = value
        else:
            previous = max(
                previous,
                value,
            )

        monotonic.append(
            previous
        )

    return monotonic


def _build_blocks(
    *,
    canonical_words: list[
        CanonicalLyricsWord
    ],
    segments: list[
        STTLyricsSegment
    ],
    assignments: list[int],
    track_duration_ms: int,
    max_block_ms: int,
    padding_ms: int,
) -> list[
    LyricsAlignmentBlock
]:
    segment_words: dict[
        int,
        list[
            CanonicalLyricsWord
        ],
    ] = {}

    for word, segment_index in zip(
        canonical_words,
        assignments,
    ):
        segment_words.setdefault(
            segment_index,
            [],
        ).append(
            word
        )

    occupied = sorted(
        segment_words
    )

    if not occupied:
        return []

    segment_groups: list[
        list[int]
    ] = []

    current: list[int] = []

    for segment_index in occupied:
        if not current:
            current = [
                segment_index
            ]
            continue

        first_segment = segments[
            current[0]
        ]

        candidate_segment = segments[
            segment_index
        ]

        candidate_span = (
            candidate_segment.end_ms
            - first_segment.start_ms
        )

        if (
            candidate_span
            <= max_block_ms
        ):
            current.append(
                segment_index
            )
        else:
            segment_groups.append(
                current
            )

            current = [
                segment_index
            ]

    if current:
        segment_groups.append(
            current
        )

    raw_blocks: list[
        tuple[
            int,
            int,
            list[
                CanonicalLyricsWord
            ],
        ]
    ] = []

    for group in segment_groups:
        first_segment = segments[
            group[0]
        ]

        last_segment = segments[
            group[-1]
        ]

        words: list[
            CanonicalLyricsWord
        ] = []

        for segment_index in group:
            words.extend(
                segment_words.get(
                    segment_index,
                    [],
                )
            )

        words.sort(
            key=lambda item: (
                item.global_index
            )
        )

        if not words:
            continue

        raw_blocks.append(
            (
                first_segment.start_ms,
                last_segment.end_ms,
                words,
            )
        )

    if not raw_blocks:
        return []

    boundaries: list[int] = []

    for index in range(
        len(
            raw_blocks
        )
        - 1
    ):
        current_end = (
            raw_blocks[
                index
            ][
                1
            ]
        )

        next_start = (
            raw_blocks[
                index + 1
            ][
                0
            ]
        )

        boundary = int(
            round(
                (
                    current_end
                    + next_start
                )
                / 2
            )
        )

        boundaries.append(
            max(
                0,
                min(
                    track_duration_ms,
                    boundary,
                ),
            )
        )

    blocks: list[
        LyricsAlignmentBlock
    ] = []

    for index, (
        raw_start,
        raw_end,
        words,
    ) in enumerate(
        raw_blocks
    ):
        if index == 0:
            start_ms = max(
                0,
                raw_start
                - padding_ms,
            )
        else:
            start_ms = boundaries[
                index - 1
            ]

        if (
            index
            == len(
                raw_blocks
            )
            - 1
        ):
            end_ms = min(
                track_duration_ms,
                raw_end
                + padding_ms,
            )
        else:
            end_ms = boundaries[
                index
            ]

        if end_ms <= start_ms:
            raise LyricsAlignmentError(
                (
                    "Invalid non-overlapping "
                    "forced-alignment block "
                    f"{index}."
                )
            )

        blocks.append(
            LyricsAlignmentBlock(
                index=index,
                start_ms=start_ms,
                end_ms=end_ms,
                words=tuple(
                    words
                ),
            )
        )

    for previous, current in zip(
        blocks,
        blocks[1:],
    ):
        if (
            previous.end_ms
            != current.start_ms
        ):
            raise LyricsAlignmentError(
                (
                    "Forced-alignment blocks "
                    "must be contiguous and "
                    "non-overlapping."
                )
            )

    flattened = [
        word.global_index
        for block in blocks
        for word in block.words
    ]

    if flattened != list(
        range(
            len(
                canonical_words
            )
        )
    ):
        raise LyricsAlignmentError(
            (
                "Forced-alignment block planning "
                "did not preserve the canonical "
                "word sequence."
            )
        )

    return blocks


def _build_timed_lines(
    *,
    plan: LyricsAlignmentPlan,
    timings: list[
        ForcedWordTiming
    ],
) -> list[
    TimedLyricsLine
]:
    grouped: dict[
        int,
        list[
            ForcedWordTiming
        ],
    ] = {
        index: []
        for index in range(
            len(
                plan.canonical_lines
            )
        )
    }

    canonical_by_index = {
        word.global_index: word
        for word in plan.canonical_words
    }

    for timing in timings:
        canonical = canonical_by_index[
            timing.global_index
        ]

        grouped[
            canonical.line_index
        ].append(
            timing
        )

    result: list[
        TimedLyricsLine
    ] = []

    for line_index, line_text in enumerate(
        plan.canonical_lines
    ):
        words = sorted(
            grouped.get(
                line_index,
                [],
            ),
            key=lambda item: (
                item.global_index
            ),
        )

        if not words:
            raise LyricsAlignmentError(
                (
                    "Forced alignment produced no words "
                    f"for lyrics line {line_index}."
                )
            )

        result.append(
            TimedLyricsLine(
                line_index=line_index,
                text=line_text,
                start_ms=words[
                    0
                ].start_ms,
                end_ms=words[
                    -1
                ].end_ms,
                words=tuple(
                    words
                ),
            )
        )

    return result


def _temporal_health(
    timings: list[
        ForcedWordTiming
    ],
    *,
    track_duration_ms: int,
) -> tuple[
    int,
    int,
    int,
    int,
    int,
]:
    non_positive = 0
    out_of_bounds = 0
    order_violations = 0
    overlap_violations = 0
    overlong = 0

    previous_start: int | None = (
        None
    )

    previous_end: int | None = (
        None
    )

    for timing in timings:
        duration = (
            timing.end_ms
            - timing.start_ms
        )

        if duration <= 0:
            non_positive += 1

        if (
            timing.start_ms < 0
            or timing.end_ms
            > track_duration_ms
        ):
            out_of_bounds += 1

        if (
            previous_start
            is not None
            and timing.start_ms
            < previous_start
        ):
            order_violations += 1

        if (
            previous_end
            is not None
            and timing.start_ms
            < (
                previous_end
                - MAX_ACCEPTABLE_WORD_OVERLAP_MS
            )
        ):
            overlap_violations += 1

        if (
            duration
            > MAX_ACCEPTABLE_WORD_DURATION_MS
        ):
            overlong += 1

        previous_start = (
            timing.start_ms
        )

        previous_end = (
            timing.end_ms
        )

    return (
        non_positive,
        out_of_bounds,
        order_violations,
        overlap_violations,
        overlong,
    )


def _normalize_word(
    value: str,
) -> str:
    normalized = (
        unicodedata.normalize(
            "NFKD",
            str(
                value
                or ""
            ),
        )
    )

    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(
            character
        )
    )

    normalized = (
        normalized
        .replace(
            "’",
            "'",
        )
        .replace(
            "‘",
            "'",
        )
        .casefold()
    )

    return "".join(
        character
        for character in normalized
        if (
            character.isalnum()
            or character == "'"
        )
    )


def _word_similarity(
    left: str,
    right: str,
) -> float:
    if not left or not right:
        return 0.0

    if left == right:
        return 1.0

    collapsed_left = (
        left.replace(
            "'",
            "",
        )
    )

    collapsed_right = (
        right.replace(
            "'",
            "",
        )
    )

    if (
        collapsed_left
        and collapsed_left
        == collapsed_right
    ):
        return 0.98

    ratio = SequenceMatcher(
        None,
        left,
        right,
        autojunk=False,
    ).ratio()

    if (
        len(
            left
        ) <= 2
        or len(
            right
        ) <= 2
    ):
        return (
            ratio
            if ratio >= 0.90
            else 0.0
        )

    return ratio


def _match_score(
    similarity: float,
) -> float:
    if similarity >= 0.999:
        return 2.4

    if (
        similarity
        >= MIN_TEXT_MATCH_SIMILARITY
    ):
        return (
            similarity
            * 1.9
        )

    return -1.35
