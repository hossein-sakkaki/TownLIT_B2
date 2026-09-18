# apps/audio_catalog/management/commands/audio_catalog_align_lyrics.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-16.
# Last Update by Hossein Sakkaki on 2026-09-18.

from __future__ import annotations

import os

from django.core.management.base import (
    BaseCommand,
    CommandError,
)

from apps.audio_catalog.models import (
    MusicLyrics,
    MusicTrackVariant,
)
from apps.audio_catalog.services.lyrics_alignment import (
    LyricsAlignmentError,
    assemble_forced_alignment,
    build_forced_alignment_plan,
)
from apps.audio_catalog.services.lyrics_forced_aligner import (
    LyricsForcedAlignerError,
    force_align_block,
)
from apps.audio_catalog.services.lyrics_processing import (
    MUSIC_LYRICS_STT_TEMPERATURE,
    build_music_lyrics_stt_prompt,
)
from apps.subtitles.services.audio_source import (
    fetch_audio_from_storage,
)
from apps.subtitles.services.stt_openai import (
    transcribe_audio,
)


class Command(BaseCommand):
    help = (
        "Dry-run TownLIT word-level lyrics forced alignment. "
        "This command never writes lyrics timing to the database."
    )

    def add_arguments(
        self,
        parser,
    ):
        parser.add_argument(
            "--track",
            required=True,
            help="MusicTrack public UUID.",
        )
        parser.add_argument(
            "--language",
            default="en",
            help="Lyrics language code.",
        )
        parser.add_argument(
            "--kind",
            default="original",
            help="Lyrics kind.",
        )
        parser.add_argument(
            "--show-lines",
            type=int,
            default=20,
            help="Number of aligned lines to print.",
        )
        parser.add_argument(
            "--show-low-confidence",
            type=int,
            default=40,
            help="Number of low-confidence words to print.",
        )

    def handle(
        self,
        *args,
        **options,
    ):
        track_public_id = str(
            options["track"]
        ).strip()

        language = (
            MusicLyrics.normalize_language_code(
                options["language"]
            )
        )

        kind = str(
            options["kind"]
        ).strip().lower()

        try:
            lyrics = (
                MusicLyrics.objects
                .select_related(
                    "track",
                    "reference_variant",
                )
                .get(
                    track__public_id=track_public_id,
                    language_code=language,
                    kind=kind,
                )
            )
        except MusicLyrics.DoesNotExist as exc:
            raise CommandError(
                "Matching lyrics document was not found."
            ) from exc

        track = lyrics.track

        variant = (
            lyrics.reference_variant
            if lyrics.reference_variant_id
            else self._default_variant(
                track_id=track.id
            )
        )

        if variant is None:
            raise CommandError(
                "No eligible playback variant was found."
            )

        if not (
            variant.audio_file
            and variant.audio_file.name
        ):
            raise CommandError(
                "Playback variant has no audio file."
            )

        canonical_text = (
            lyrics.plain_text
            or ""
        ).strip()

        if not canonical_text:
            raise CommandError(
                "Lyrics document has no canonical plain text."
            )

        duration_ms = int(
            variant.duration_ms
            or track.duration_ms
            or 0
        )

        if duration_ms <= 0:
            raise CommandError(
                "Track duration is not available."
            )

        max_block_ms = int(
            float(
                os.environ.get(
                    "LYRICS_ALIGNMENT_MAX_BLOCK_SECONDS",
                    "30",
                )
            )
            * 1000
        )

        padding_ms = int(
            float(
                os.environ.get(
                    "LYRICS_ALIGNMENT_BLOCK_PADDING_SECONDS",
                    "1.5",
                )
            )
            * 1000
        )

        local_audio_path = None

        try:
            local_audio_path = (
                fetch_audio_from_storage(
                    variant.audio_file
                )
            )

            self._print_source(
                lyrics=lyrics,
                variant=variant,
                duration_ms=duration_ms,
            )

            self.stdout.write(
                "\nRunning TownLIT STT with canonical lyrics context "
                "for rough segment anchors..."
            )

            stt = transcribe_audio(
                wav_path=local_audio_path,
                language=(
                    lyrics.language_code
                    or track.language_code
                    or None
                ),
                prompt=build_music_lyrics_stt_prompt(
                    canonical_text
                ),
                temperature=MUSIC_LYRICS_STT_TEMPERATURE,
            )

            segments = (
                stt.get("segments", [])
                or []
            )

            self.stdout.write(
                f"STT model                    : "
                f"{stt.get('model', '')}"
            )

            self.stdout.write(
                f"STT segments                 : "
                f"{len(segments)}"
            )

            plan = build_forced_alignment_plan(
                canonical_text=canonical_text,
                stt_segments=segments,
                track_duration_ms=duration_ms,
                max_block_ms=max_block_ms,
                padding_ms=padding_ms,
            )

            self.stdout.write(
                "\nALIGNMENT PLAN"
            )
            self.stdout.write(
                "canonical words              : "
                f"{len(plan.canonical_words)}"
            )
            self.stdout.write(
                "direct STT matches           : "
                f"{plan.direct_match_count}"
            )
            self.stdout.write(
                "text match ratio             : "
                f"{plan.text_match_ratio:.2%}"
            )
            self.stdout.write(
                "forced-alignment blocks      : "
                f"{len(plan.blocks)}"
            )

            all_timings = []

            for block in plan.blocks:
                self.stdout.write(
                    f"\nBlock {block.index + 1}/"
                    f"{len(plan.blocks)} "
                    f"{block.start_ms} → {block.end_ms} ms "
                    f"({len(block.words)} words)"
                )

                timings = force_align_block(
                    audio_path=local_audio_path,
                    block=block,
                )

                all_timings.extend(
                    timings
                )

                if timings:
                    mean_confidence = (
                        sum(
                            item.confidence
                            for item in timings
                        )
                        / len(timings)
                    )

                    self.stdout.write(
                        "  block confidence           : "
                        f"{mean_confidence:.4f}"
                    )

            result = assemble_forced_alignment(
                plan=plan,
                timings=all_timings,
                track_duration_ms=duration_ms,
            )

            self._print_result(
                result=result,
                show_lines=max(
                    0,
                    int(options["show_lines"]),
                ),
                show_low_confidence=max(
                    0,
                    int(
                        options[
                            "show_low_confidence"
                        ]
                    ),
                ),
            )

        except (
            LyricsAlignmentError,
            LyricsForcedAlignerError,
        ) as exc:
            raise CommandError(
                str(exc)
            ) from exc

        finally:
            if (
                local_audio_path
                and os.path.exists(
                    local_audio_path
                )
            ):
                try:
                    os.unlink(
                        local_audio_path
                    )
                except OSError:
                    pass

    @staticmethod
    def _default_variant(
        *,
        track_id: int,
    ):
        return (
            MusicTrackVariant.objects
            .filter(
                track_id=track_id,
                is_active=True,
                is_converted=True,
                is_streamable=True,
            )
            .exclude(audio_file="")
            .order_by(
                "-is_default",
                "sort_order",
                "id",
            )
            .first()
        )

    def _print_source(
        self,
        *,
        lyrics,
        variant,
        duration_ms: int,
    ) -> None:
        self.stdout.write(
            "=" * 100
        )
        self.stdout.write(
            "TOWNLIT MUSIC LYRICS — FORCED ALIGNMENT DRY RUN"
        )
        self.stdout.write(
            "=" * 100
        )

        self.stdout.write(
            "\nSOURCE"
        )
        self.stdout.write(
            f"track                        : "
            f"{lyrics.track.title}"
        )
        self.stdout.write(
            f"track_public_id              : "
            f"{lyrics.track.public_id}"
        )
        self.stdout.write(
            f"variant_public_id            : "
            f"{variant.public_id}"
        )
        self.stdout.write(
            f"duration_ms                  : "
            f"{duration_ms}"
        )
        self.stdout.write(
            f"lyrics_public_id             : "
            f"{lyrics.public_id}"
        )
        self.stdout.write(
            f"lyrics_status                : "
            f"{lyrics.status}"
        )
        self.stdout.write(
            f"lyrics_timing_mode           : "
            f"{lyrics.timing_mode}"
        )

    def _print_result(
        self,
        *,
        result,
        show_lines: int,
        show_low_confidence: int,
    ) -> None:
        self.stdout.write(
            "\nFINAL QUALITY"
        )
        self.stdout.write(
            "canonical_word_count         : "
            f"{result.canonical_word_count}"
        )
        self.stdout.write(
            "text_match_ratio             : "
            f"{result.text_match_ratio:.2%}"
        )
        self.stdout.write(
            "mean_alignment_confidence    : "
            f"{result.mean_alignment_confidence:.4f}"
        )
        self.stdout.write(
            "low_confidence_word_count    : "
            f"{result.low_confidence_word_count}"
        )
        self.stdout.write(
            "non_positive_duration_count  : "
            f"{result.non_positive_duration_count}"
        )
        self.stdout.write(
            "out_of_bounds_count          : "
            f"{result.out_of_bounds_count}"
        )
        self.stdout.write(
            "order_violation_count        : "
            f"{result.order_violation_count}"
        )
        self.stdout.write(
            "overlap_violation_count      : "
            f"{result.overlap_violation_count}"
        )
        self.stdout.write(
            "overlong_word_count          : "
            f"{result.overlong_word_count}"
        )
        self.stdout.write(
            "acceptable                   : "
            f"{result.is_acceptable}"
        )

        self.stdout.write(
            "\nALIGNED LINES"
        )

        for line in result.lines[:show_lines]:
            self.stdout.write(
                f"\n[{line.line_index:03}] "
                f"{line.start_ms:>7} → "
                f"{line.end_ms:>7} | "
                f"{line.text}"
            )

            for word in line.words:
                self.stdout.write(
                    f"    "
                    f"{word.start_ms:>7} → "
                    f"{word.end_ms:>7} | "
                    f"{word.text:<18} | "
                    f"conf={word.confidence:.3f}"
                )

        low_confidence = sorted(
            [
                word
                for word in result.words
                if word.confidence < 0.25
            ],
            key=lambda item: (
                item.confidence,
                item.global_index,
            ),
        )

        self.stdout.write(
            "\nLOW-CONFIDENCE WORDS"
        )

        for word in low_confidence[:show_low_confidence]:
            self.stdout.write(
                f"index={word.global_index:03} "
                f"{word.start_ms:>7} → "
                f"{word.end_ms:>7} | "
                f"{word.text!r} | "
                f"confidence={word.confidence:.4f}"
            )

        self.stdout.write(
            "\nDATABASE"
        )
        self.stdout.write(
            "NO DATABASE WRITES WERE PERFORMED."
        )
        self.stdout.write(
            "=" * 100
        )