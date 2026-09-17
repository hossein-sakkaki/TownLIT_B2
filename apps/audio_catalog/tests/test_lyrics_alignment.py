# apps/audio_catalog/tests/test_lyrics_alignment.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-16.
# Last Update by Hossein Sakkaki on 2026-09-16.

from django.test import (
    SimpleTestCase,
)

from apps.audio_catalog.services.lyrics_alignment import (
    ForcedWordTiming,
    assemble_forced_alignment,
    build_forced_alignment_plan,
)


class LyricsAlignmentTests(
    SimpleTestCase
):
    databases = set()

    def test_plan_preserves_repeated_chorus_order(
        self,
    ):
        plan = (
            build_forced_alignment_plan(
                canonical_text=(
                    "Hallelujah amen\n"
                    "Grace today\n"
                    "Hallelujah amen"
                ),
                stt_segments=[
                    {
                        "start": 1.0,
                        "end": 3.0,
                        "text": (
                            "Hallelujah amen"
                        ),
                    },
                    {
                        "start": 4.0,
                        "end": 6.0,
                        "text": (
                            "Grace today"
                        ),
                    },
                    {
                        "start": 7.0,
                        "end": 9.0,
                        "text": (
                            "Hallelujah amen"
                        ),
                    },
                ],
                track_duration_ms=10_000,
                max_block_ms=4_000,
                padding_ms=0,
            )
        )

        self.assertEqual(
            [
                word.text
                for block in plan.blocks
                for word in block.words
            ],
            [
                "Hallelujah",
                "amen",
                "Grace",
                "today",
                "Hallelujah",
                "amen",
            ],
        )

        self.assertEqual(
            plan.direct_match_count,
            6,
        )

        self.assertEqual(
            plan.text_match_ratio,
            1.0,
        )

    def test_plan_assigns_missing_stt_word_without_losing_canonical_word(
        self,
    ):
        plan = (
            build_forced_alignment_plan(
                canonical_text=(
                    "Show me a clear sign today"
                ),
                stt_segments=[
                    {
                        "start": 1.0,
                        "end": 4.0,
                        "text": (
                            "Show me clear sign today"
                        ),
                    },
                ],
                track_duration_ms=5_000,
                padding_ms=0,
            )
        )

        self.assertEqual(
            [
                word.text
                for word in plan.blocks[
                    0
                ].words
            ],
            [
                "Show",
                "me",
                "a",
                "clear",
                "sign",
                "today",
            ],
        )

        self.assertEqual(
            plan.direct_match_count,
            5,
        )

        self.assertAlmostEqual(
            plan.text_match_ratio,
            5 / 6,
            places=5,
        )

    def test_plan_rejects_transcript_below_safe_match_threshold(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            (
                "does not match canonical lyrics "
                "well enough"
            ),
        ):
            build_forced_alignment_plan(
                canonical_text=(
                    "Show me a sign"
                ),
                stt_segments=[
                    {
                        "start": 1.0,
                        "end": 3.0,
                        "text": (
                            "Show me sign"
                        ),
                    },
                ],
                track_duration_ms=5_000,
                padding_ms=0,
            )

    def test_plan_builds_short_audio_blocks(
        self,
    ):
        plan = (
            build_forced_alignment_plan(
                canonical_text=(
                    "one two\n"
                    "three four\n"
                    "five six"
                ),
                stt_segments=[
                    {
                        "start": 0.0,
                        "end": 8.0,
                        "text": "one two",
                    },
                    {
                        "start": 9.0,
                        "end": 17.0,
                        "text": "three four",
                    },
                    {
                        "start": 18.0,
                        "end": 27.0,
                        "text": "five six",
                    },
                ],
                track_duration_ms=30_000,
                max_block_ms=18_000,
                padding_ms=0,
            )
        )

        self.assertEqual(
            len(
                plan.blocks
            ),
            2,
        )

        self.assertEqual(
            [
                len(
                    block.words
                )
                for block in plan.blocks
            ],
            [
                4,
                2,
            ],
        )

    def test_assemble_preserves_canonical_line_text(
        self,
    ):
        plan = (
            build_forced_alignment_plan(
                canonical_text=(
                    "Show me a sign\n"
                    "Of Your goodness"
                ),
                stt_segments=[
                    {
                        "start": 1.0,
                        "end": 4.0,
                        "text": (
                            "Show me a sign "
                            "of your goodness"
                        ),
                    },
                ],
                track_duration_ms=5_000,
                padding_ms=0,
            )
        )

        timings = []

        cursor = 1_000

        for word in (
            plan.canonical_words
        ):
            timings.append(
                ForcedWordTiming(
                    global_index=(
                        word.global_index
                    ),
                    text=word.text,
                    start_ms=cursor,
                    end_ms=cursor + 300,
                    confidence=0.95,
                    provider_metadata={},
                )
            )

            cursor += 350

        result = (
            assemble_forced_alignment(
                plan=plan,
                timings=timings,
                track_duration_ms=5_000,
            )
        )

        self.assertEqual(
            [
                line.text
                for line in result.lines
            ],
            [
                "Show me a sign",
                "Of Your goodness",
            ],
        )

        self.assertEqual(
            result.temporal_violation_count,
            0,
        )

        self.assertTrue(
            result.is_acceptable
        )

    def test_assemble_rejects_word_identity_mismatch(
        self,
    ):
        plan = (
            build_forced_alignment_plan(
                canonical_text="Grace today",
                stt_segments=[
                    {
                        "start": 1.0,
                        "end": 2.0,
                        "text": (
                            "Grace today"
                        ),
                    },
                ],
                track_duration_ms=3_000,
                padding_ms=0,
            )
        )

        timings = [
            ForcedWordTiming(
                global_index=0,
                text="Wrong",
                start_ms=1_000,
                end_ms=1_300,
                confidence=0.9,
                provider_metadata={},
            ),
            ForcedWordTiming(
                global_index=1,
                text="today",
                start_ms=1_400,
                end_ms=1_800,
                confidence=0.9,
                provider_metadata={},
            ),
        ]

        with self.assertRaises(
            ValueError
        ):
            assemble_forced_alignment(
                plan=plan,
                timings=timings,
                track_duration_ms=3_000,
            )

    def test_temporal_health_detects_large_overlap(
        self,
    ):
        plan = (
            build_forced_alignment_plan(
                canonical_text="Grace today",
                stt_segments=[
                    {
                        "start": 1.0,
                        "end": 3.0,
                        "text": (
                            "Grace today"
                        ),
                    },
                ],
                track_duration_ms=4_000,
                padding_ms=0,
            )
        )

        timings = [
            ForcedWordTiming(
                global_index=0,
                text="Grace",
                start_ms=1_000,
                end_ms=2_000,
                confidence=0.9,
                provider_metadata={},
            ),
            ForcedWordTiming(
                global_index=1,
                text="today",
                start_ms=1_500,
                end_ms=2_500,
                confidence=0.9,
                provider_metadata={},
            ),
        ]

        result = (
            assemble_forced_alignment(
                plan=plan,
                timings=timings,
                track_duration_ms=4_000,
            )
        )

        self.assertEqual(
            result.overlap_violation_count,
            1,
        )

        self.assertFalse(
            result.is_acceptable
        )
        

    def test_alignment_blocks_are_contiguous_and_non_overlapping(
        self,
    ):
        plan = (
            build_forced_alignment_plan(
                canonical_text=(
                    "one two\n"
                    "three four\n"
                    "five six"
                ),
                stt_segments=[
                    {
                        "start": 1.0,
                        "end": 8.0,
                        "text": "one two",
                    },
                    {
                        "start": 9.0,
                        "end": 17.0,
                        "text": "three four",
                    },
                    {
                        "start": 18.0,
                        "end": 27.0,
                        "text": "five six",
                    },
                ],
                track_duration_ms=30_000,
                max_block_ms=10_000,
                padding_ms=1_500,
            )
        )

        self.assertGreater(
            len(
                plan.blocks
            ),
            1,
        )

        for previous, current in zip(
            plan.blocks,
            plan.blocks[
                1:
            ],
        ):
            self.assertEqual(
                previous.end_ms,
                current.start_ms,
            )

            self.assertLessEqual(
                previous.end_ms,
                current.start_ms,
            )