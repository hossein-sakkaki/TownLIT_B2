# apps/audio_catalog/admin/lyrics.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-14.
# Last Update by Hossein Sakkaki on 2026-09-18.

from __future__ import annotations

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.forms.models import BaseInlineFormSet
from django.utils.html import format_html_join

from apps.audio_catalog.models.lyrics import MusicLyrics, MusicLyricsLine
from apps.audio_catalog.services.lyrics_processing import (
    LyricsAlignmentNotEligibleError,
)
from apps.audio_catalog.tasks import enqueue_music_lyrics_alignment

from .shared import LargeResultAdminMixin


class MusicLyricsLineInlineFormSet(BaseInlineFormSet):
    """Validate ordering rules that cannot be expressed as row constraints."""

    def clean(self):
        super().clean()

        if any(self.errors):
            return

        rows: list[tuple[int, int | None, int | None]] = []

        for form in self.forms:
            cleaned = getattr(form, "cleaned_data", None) or {}

            if cleaned.get("DELETE"):
                continue

            sequence = cleaned.get("sequence")
            start_ms = cleaned.get("start_ms")
            end_ms = cleaned.get("end_ms")

            if sequence is None:
                continue

            rows.append((int(sequence), start_ms, end_ms))

        if self.instance.timing_mode != MusicLyrics.TimingMode.LINE:
            return

        rows.sort(key=lambda row: row[0])
        previous_start: int | None = None

        for _, start_ms, _ in rows:
            if start_ms is None:
                continue

            if previous_start is not None and start_ms <= previous_start:
                raise ValidationError(
                    "Synchronized lyrics line start times must increase "
                    "strictly in sequence order."
                )

            previous_start = start_ms

        for index, (_, _, end_ms) in enumerate(rows[:-1]):
            next_start_ms = rows[index + 1][1]

            if (
                end_ms is not None
                and next_start_ms is not None
                and end_ms > next_start_ms
            ):
                raise ValidationError(
                    "A lyrics line cannot end after the next line starts."
                )


class MusicLyricsLineInline(admin.TabularInline):
    model = MusicLyricsLine
    formset = MusicLyricsLineInlineFormSet
    extra = 0

    fields = (
        "sequence",
        "start_ms",
        "end_ms",
        "text",
        "word_count",
        "public_id",
    )
    readonly_fields = (
        "word_count",
        "public_id",
    )
    ordering = (
        "sequence",
        "id",
    )

    @admin.display(description="Words")
    def word_count(self, obj) -> int:
        if not obj.pk:
            return 0
        return obj.words.count()


@admin.action(description="Queue adaptive word-level alignment")
def queue_automatic_alignment(modeladmin, request, queryset):
    queued = 0
    skipped = 0
    failures: list[str] = []

    for lyrics in (
        queryset
        .select_related("track", "reference_variant")
        .iterator(chunk_size=100)
    ):
        try:
            enqueue_music_lyrics_alignment(lyrics)
            queued += 1
        except LyricsAlignmentNotEligibleError:
            skipped += 1
        except Exception as exc:
            failures.append(f"{lyrics}: {exc}")

    if queued:
        modeladmin.message_user(
            request,
            (
                f"{queued} lyrics document(s) queued for adaptive "
                "word alignment."
            ),
            level=messages.SUCCESS,
        )

    if skipped:
        modeladmin.message_user(
            request,
            (
                f"{skipped} lyrics document(s) were skipped. "
                "Automatic alignment requires plain canonical lyrics "
                "with no existing timed lines."
            ),
            level=messages.WARNING,
        )

    if failures:
        modeladmin.message_user(
            request,
            " | ".join(failures[:10]),
            level=messages.ERROR,
        )


@admin.register(MusicLyrics)
class MusicLyricsAdmin(LargeResultAdminMixin, admin.ModelAdmin):
    list_display = (
        "track",
        "language_code",
        "kind",
        "timing_mode",
        "status",
        "is_default",
        "line_count",
        "word_count",
        "alignment_state",
        "alignment_quality",
        "published_at",
        "updated_at",
    )

    list_filter = (
        "status",
        "timing_mode",
        "kind",
        "is_default",
        "language_code",
    )

    search_fields = (
        "track__title",
        "track__subtitle",
        "plain_text",
        "source_label",
        "public_id",
    )

    readonly_fields = (
        "alignment_state",
        "alignment_quality",
        "alignment_details",
        "public_id",
        "published_at",
        "created_at",
        "updated_at",
    )

    autocomplete_fields = (
        "track",
        "reference_variant",
        "rights_record",
    )

    inlines = (MusicLyricsLineInline,)
    actions = (queue_automatic_alignment,)

    fieldsets = (
        (
            "Track",
            {
                "fields": (
                    "track",
                    "reference_variant",
                    "rights_record",
                ),
            },
        ),
        (
            "Lyrics",
            {
                "fields": (
                    "language_code",
                    "kind",
                    "status",
                    "timing_mode",
                    "timing_offset_ms",
                    "is_default",
                    "plain_text",
                ),
            },
        ),
        (
            "Automatic alignment",
            {
                "fields": (
                    "alignment_state",
                    "alignment_quality",
                    "alignment_details",
                ),
            },
        ),
        (
            "Source",
            {
                "classes": ("collapse",),
                "fields": (
                    "source_label",
                    "source_url",
                    "metadata",
                ),
            },
        ),
        (
            "System",
            {
                "classes": ("collapse",),
                "fields": (
                    "public_id",
                    "published_at",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "track",
                "reference_variant",
                "rights_record",
            )
            .prefetch_related("lines__words")
        )

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        if obj.is_default and obj.track_id:
            (
                MusicLyrics.objects
                .filter(
                    track_id=obj.track_id,
                    is_default=True,
                )
                .exclude(pk=obj.pk)
                .update(
                    is_default=False,
                    default_slot=None,
                )
            )

        super().save_model(request, obj, form, change)

    @admin.display(description="Lines")
    def line_count(self, obj) -> int:
        return len(list(obj.lines.all()))

    @admin.display(description="Words")
    def word_count(self, obj) -> int:
        return sum(
            len(list(line.words.all()))
            for line in obj.lines.all()
        )

    @admin.display(description="Alignment")
    def alignment_state(self, obj) -> str:
        alignment = self._alignment(obj)
        state = str(alignment.get("state", "not_started") or "not_started")
        processing_state = str(alignment.get("processing_state", "") or "")

        if processing_state and processing_state != "idle":
            return f"{state} / {processing_state}"

        return state

    @admin.display(description="Quality")
    def alignment_quality(self, obj) -> str:
        alignment = self._alignment(obj)
        value = alignment.get(
            "mean_alignment_confidence",
            alignment.get("quality_score"),
        )

        if value is None:
            return "—"

        try:
            confidence = float(value) * 100
        except (TypeError, ValueError):
            return "—"

        parts = [f"{confidence:.1f}% confidence"]

        text_ratio = alignment.get(
            "text_match_ratio",
            alignment.get("direct_match_ratio"),
        )

        try:
            parts.append(f"{float(text_ratio) * 100:.1f}% text")
        except (TypeError, ValueError):
            pass

        low_ratio = self._low_confidence_ratio(alignment)

        if low_ratio is not None:
            parts.append(f"{low_ratio * 100:.1f}% low")

        return " · ".join(parts)

    @admin.display(description="Alignment details")
    def alignment_details(self, obj) -> str:
        alignment = self._alignment(obj)

        if not alignment:
            return "Automatic alignment has not been run."

        fields = (
            ("State", alignment.get("state")),
            ("Processing", alignment.get("processing_state")),
            ("Strategy", alignment.get("strategy")),
            ("Strategy version", alignment.get("strategy_version")),
            ("Attempts", alignment.get("attempt_count")),
            (
                "Selected max block",
                self._format_block_ms(alignment.get("selected_max_block_ms")),
            ),
            (
                "Best failed block",
                self._format_block_ms(alignment.get("best_max_block_ms")),
            ),
            ("Provider", alignment.get("provider")),
            ("Model", alignment.get("model")),
            ("Model license", alignment.get("model_license")),
            ("STT model", alignment.get("stt_model")),
            ("Reference variant", alignment.get("reference_variant_id")),
            ("Canonical words", alignment.get("canonical_word_count")),
            ("Direct matches", alignment.get("direct_match_count")),
            (
                "Text match ratio",
                alignment.get(
                    "text_match_ratio",
                    alignment.get("direct_match_ratio"),
                ),
            ),
            (
                "Mean confidence",
                alignment.get(
                    "mean_alignment_confidence",
                    alignment.get("quality_score"),
                ),
            ),
            ("Low-confidence words", alignment.get("low_confidence_word_count")),
            ("Low-confidence ratio", self._low_confidence_ratio(alignment)),
            (
                "Non-positive durations",
                alignment.get("non_positive_duration_count"),
            ),
            ("Out of bounds", alignment.get("out_of_bounds_count")),
            ("Order violations", alignment.get("order_violation_count")),
            ("Overlap violations", alignment.get("overlap_violation_count")),
            ("Overlong words", alignment.get("overlong_word_count")),
            ("Lines", alignment.get("line_count")),
            ("Words", alignment.get("word_count")),
            ("Candidate lines", alignment.get("candidate_line_count")),
            ("Candidate words", alignment.get("candidate_word_count")),
            ("Completed", alignment.get("completed_at")),
            ("Last attempt", alignment.get("last_attempt_at")),
            ("Last error", alignment.get("last_error")),
        )

        lines = [
            f"{label}: {value}"
            for label, value in fields
            if value not in {None, ""}
        ]

        attempts = alignment.get("attempts")

        if isinstance(attempts, list) and attempts:
            lines.append("Adaptive attempts:")

            for index, attempt in enumerate(attempts, start=1):
                if not isinstance(attempt, dict):
                    continue
                lines.append(
                    f"  {index}. {self._format_attempt(attempt)}"
                )

        return format_html_join(
            "",
            "<div>{}</div>",
            ((line,) for line in lines),
        )

    @staticmethod
    def _alignment(obj) -> dict:
        metadata = obj.metadata if isinstance(obj.metadata, dict) else {}
        alignment = metadata.get("alignment", {})
        return alignment if isinstance(alignment, dict) else {}

    @staticmethod
    def _low_confidence_ratio(alignment: dict) -> float | None:
        value = alignment.get("low_confidence_ratio")

        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        count = alignment.get("low_confidence_word_count")
        total = alignment.get("canonical_word_count")

        try:
            count_value = int(count)
            total_value = int(total)
        except (TypeError, ValueError):
            return None

        if total_value <= 0:
            return None

        return count_value / total_value

    @staticmethod
    def _format_block_ms(value) -> str | None:
        if value in {None, ""}:
            return None

        try:
            milliseconds = int(value)
        except (TypeError, ValueError):
            return str(value)

        return f"{milliseconds / 1000:g}s"

    @classmethod
    def _format_attempt(cls, attempt: dict) -> str:
        block = cls._format_block_ms(attempt.get("max_block_ms")) or "?"
        pieces = [
            f"block={block}",
            f"blocks={attempt.get('block_count', '—')}",
            f"acceptable={attempt.get('acceptable', False)}",
        ]

        text_ratio = attempt.get("text_match_ratio")
        mean_confidence = attempt.get("mean_alignment_confidence")
        low_ratio = attempt.get("low_confidence_ratio")

        try:
            pieces.append(f"text={float(text_ratio) * 100:.1f}%")
        except (TypeError, ValueError):
            pass

        try:
            pieces.append(f"confidence={float(mean_confidence) * 100:.1f}%")
        except (TypeError, ValueError):
            pass

        try:
            pieces.append(f"low={float(low_ratio) * 100:.1f}%")
        except (TypeError, ValueError):
            pass

        failures = attempt.get("quality_gate_failures")
        if isinstance(failures, list) and failures:
            pieces.append("gates=" + ", ".join(str(value) for value in failures))

        error = str(attempt.get("error", "") or "").strip()
        if error:
            pieces.append(f"error={error}")

        return " · ".join(pieces)
