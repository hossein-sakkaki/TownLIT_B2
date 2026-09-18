# apps/audio_catalog/management/commands/audio_catalog_align_lyrics.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-16.
# Last Update by Hossein Sakkaki on 2026-09-18.

from __future__ import annotations

import os

from django.core.management.base import BaseCommand, CommandError

from apps.audio_catalog.models import MusicLyrics, MusicTrackVariant
from apps.audio_catalog.services.lyrics_alignment import (
    LOW_CONFIDENCE_THRESHOLD,
)
from apps.audio_catalog.services.lyrics_forced_aligner import (
    LyricsForcedAlignerError,
)
from apps.audio_catalog.services.lyrics_processing import (
    MUSIC_LYRICS_STT_TEMPERATURE,
    LyricsAlignmentProcessingError,
    build_music_lyrics_stt_prompt,
    configured_alignment_block_sizes_ms,
    configured_alignment_padding_ms,
    evaluate_adaptive_music_lyrics_alignment,
)
from apps.subtitles.services.audio_source import fetch_audio_from_storage
from apps.subtitles.services.stt_openai import transcribe_audio


class Command(BaseCommand):
    help = (
        "Dry-run TownLIT adaptive word-level lyrics forced alignment. "
        "This command never writes lyrics timing to the database."
    )

    def add_arguments(self, parser):
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

    def handle(self, *args, **options):
        track_public_id = str(options["track"]).strip()
        language = MusicLyrics.normalize_language_code(options["language"])
        kind = str(options["kind"]).strip().lower()

        try:
            lyrics = (
                MusicLyrics.objects
                .select_related("track", "reference_variant")
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
            else self._default_variant(track_id=track.id)
        )

        if variant is None:
            raise CommandError(
                "No eligible playback variant was found."
            )

        if not (variant.audio_file and variant.audio_file.name):
            raise CommandError(
                "Playback variant has no audio file."
            )

        canonical_text = (lyrics.plain_text or "").strip()

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

        local_audio_path: str | None = None

        try:
            block_sizes_ms = configured_alignment_block_sizes_ms()
            padding_ms = configured_alignment_padding_ms()

            local_audio_path = fetch_audio_from_storage(variant.audio_file)

            self._print_source(
                lyrics=lyrics,
                variant=variant,
                duration_ms=duration_ms,
                block_sizes_ms=block_sizes_ms,
                padding_ms=padding_ms,
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
                prompt=build_music_lyrics_stt_prompt(canonical_text),
                temperature=MUSIC_LYRICS_STT_TEMPERATURE,
            )

            segments = stt.get("segments", []) or []

            self.stdout.write(
                f"STT model                    : {stt.get('model', '')}"
            )
            self.stdout.write(
                f"STT segments                 : {len(segments)}"
            )

            evaluation = evaluate_adaptive_music_lyrics_alignment(
                canonical_text=canonical_text,
                stt_segments=segments,
                audio_path=local_audio_path,
                track_duration_ms=duration_ms,
                block_sizes_ms=block_sizes_ms,
                padding_ms=padding_ms,
            )

            self._print_attempts(evaluation)

            selected_attempt = evaluation.selected_attempt
            display_attempt = selected_attempt or evaluation.best_attempt

            if display_attempt is None or display_attempt.result is None:
                self.stdout.write("\nFINAL QUALITY")
                self.stdout.write("No complete forced-alignment result was produced.")
                self._print_database_footer()
                raise CommandError(
                    "Adaptive lyrics alignment produced no complete result."
                )

            self._print_result(
                result=display_attempt.result,
                selected_max_block_ms=(
                    selected_attempt.max_block_ms
                    if selected_attempt is not None
                    else None
                ),
                show_lines=max(0, int(options["show_lines"])),
                show_low_confidence=max(
                    0,
                    int(options["show_low_confidence"]),
                ),
            )

            self._print_database_footer()

        except (LyricsAlignmentProcessingError, LyricsForcedAlignerError) as exc:
            raise CommandError(str(exc)) from exc

        finally:
            if local_audio_path and os.path.exists(local_audio_path):
                try:
                    os.unlink(local_audio_path)
                except OSError:
                    pass

    @staticmethod
    def _default_variant(*, track_id: int):
        return (
            MusicTrackVariant.objects
            .filter(
                track_id=track_id,
                is_active=True,
                is_converted=True,
                is_streamable=True,
            )
            .exclude(audio_file="")
            .order_by("-is_default", "sort_order", "id")
            .first()
        )

    def _print_source(
        self,
        *,
        lyrics,
        variant,
        duration_ms: int,
        block_sizes_ms: tuple[int, ...],
        padding_ms: int,
    ) -> None:
        self.stdout.write("=" * 100)
        self.stdout.write(
            "TOWNLIT MUSIC LYRICS — ADAPTIVE FORCED ALIGNMENT DRY RUN"
        )
        self.stdout.write("=" * 100)

        self.stdout.write("\nSOURCE")
        self.stdout.write(f"track                        : {lyrics.track.title}")
        self.stdout.write(f"track_public_id              : {lyrics.track.public_id}")
        self.stdout.write(f"variant_public_id            : {variant.public_id}")
        self.stdout.write(f"duration_ms                  : {duration_ms}")
        self.stdout.write(f"lyrics_public_id             : {lyrics.public_id}")
        self.stdout.write(f"lyrics_status                : {lyrics.status}")
        self.stdout.write(f"lyrics_timing_mode           : {lyrics.timing_mode}")

        self.stdout.write("\nSTRATEGY")
        self.stdout.write(
            "block sizes                  : "
            + " → ".join(self._format_block_ms(value) for value in block_sizes_ms)
        )
        self.stdout.write(
            f"boundary padding             : {padding_ms / 1000:g}s"
        )

    def _print_attempts(self, evaluation) -> None:
        self.stdout.write("\nADAPTIVE ATTEMPTS")

        for index, attempt in enumerate(evaluation.attempts, start=1):
            label = self._format_block_ms(attempt.max_block_ms)
            selected = (
                evaluation.selected_attempt_index is not None
                and evaluation.selected_attempt_index == index - 1
            )

            self.stdout.write(
                f"\nAttempt {index}: max block {label}"
                + (" [SELECTED]" if selected else "")
            )
            self.stdout.write(f"  blocks                     : {attempt.block_count}")
            self.stdout.write(
                f"  direct STT matches         : {attempt.direct_match_count}"
            )
            self.stdout.write(
                f"  text match ratio           : {attempt.text_match_ratio:.2%}"
            )

            if attempt.error:
                self.stdout.write(f"  error                      : {attempt.error}")
                continue

            result = attempt.result

            if result is None:
                self.stdout.write("  result                     : unavailable")
                continue

            self.stdout.write(
                "  mean confidence            : "
                f"{result.mean_alignment_confidence:.4f}"
            )
            self.stdout.write(
                "  low-confidence ratio       : "
                f"{result.low_confidence_ratio:.2%}"
            )
            self.stdout.write(
                "  temporal violations        : "
                f"{result.temporal_violation_count}"
            )
            self.stdout.write(
                f"  overlong words             : {result.overlong_word_count}"
            )
            self.stdout.write(
                f"  acceptable                 : {result.is_acceptable}"
            )

            if result.quality_gate_failures:
                self.stdout.write(
                    "  failed gates               : "
                    + ", ".join(result.quality_gate_failures)
                )

    def _print_result(
        self,
        *,
        result,
        selected_max_block_ms: int | None,
        show_lines: int,
        show_low_confidence: int,
    ) -> None:
        self.stdout.write("\nFINAL QUALITY")
        self.stdout.write(
            "selected_max_block           : "
            + (
                self._format_block_ms(selected_max_block_ms)
                if selected_max_block_ms is not None
                else "NONE — showing best failed attempt"
            )
        )
        self.stdout.write(
            f"canonical_word_count         : {result.canonical_word_count}"
        )
        self.stdout.write(
            f"text_match_ratio             : {result.text_match_ratio:.2%}"
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
            f"low_confidence_ratio         : {result.low_confidence_ratio:.2%}"
        )
        self.stdout.write(
            "non_positive_duration_count  : "
            f"{result.non_positive_duration_count}"
        )
        self.stdout.write(
            f"out_of_bounds_count          : {result.out_of_bounds_count}"
        )
        self.stdout.write(
            f"order_violation_count        : {result.order_violation_count}"
        )
        self.stdout.write(
            f"overlap_violation_count      : {result.overlap_violation_count}"
        )
        self.stdout.write(
            f"overlong_word_count          : {result.overlong_word_count}"
        )
        self.stdout.write(
            f"acceptable                   : {result.is_acceptable}"
        )

        if result.quality_gate_failures:
            self.stdout.write(
                "failed_gates                 : "
                + ", ".join(result.quality_gate_failures)
            )

        self.stdout.write("\nALIGNED LINES")

        for line in result.lines[:show_lines]:
            self.stdout.write(
                f"\n[{line.line_index:03}] "
                f"{line.start_ms:>7} → {line.end_ms:>7} | {line.text}"
            )

            for word in line.words:
                self.stdout.write(
                    f"    {word.start_ms:>7} → {word.end_ms:>7} | "
                    f"{word.text:<18} | conf={word.confidence:.3f}"
                )

        low_confidence = sorted(
            [word for word in result.words if word.confidence < LOW_CONFIDENCE_THRESHOLD],
            key=lambda item: (item.confidence, item.global_index),
        )

        self.stdout.write("\nLOW-CONFIDENCE WORDS")

        for word in low_confidence[:show_low_confidence]:
            self.stdout.write(
                f"index={word.global_index:03} "
                f"{word.start_ms:>7} → {word.end_ms:>7} | "
                f"{word.text!r} | confidence={word.confidence:.4f}"
            )

    def _print_database_footer(self) -> None:
        self.stdout.write("\nDATABASE")
        self.stdout.write("NO DATABASE WRITES WERE PERFORMED.")
        self.stdout.write("=" * 100)

    @staticmethod
    def _format_block_ms(value: int) -> str:
        return f"{value / 1000:g}s"
