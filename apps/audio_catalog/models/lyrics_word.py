# apps/audio_catalog/models/lyrics_word.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-16.
# Last Update by Hossein Sakkaki on 2026-09-16.

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from .base import PublicIDTimestampedModel


class MusicLyricsWord(
    PublicIDTimestampedModel
):
    """
    One canonical lyrics word with playback timing.

    Word text belongs to TownLIT's canonical lyrics.
    STT supplies timing evidence only.
    """

    line = models.ForeignKey(
        "audio_catalog.MusicLyricsLine",
        on_delete=models.CASCADE,
        related_name="words",
    )

    sequence = models.PositiveIntegerField()

    text = models.CharField(
        max_length=180,
    )

    start_ms = models.PositiveIntegerField()

    end_ms = models.PositiveIntegerField()

    confidence = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
    )

    is_inferred = models.BooleanField(
        default=False,
        db_index=True,
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    def clean(self) -> None:
        super().clean()

        self.text = (
            self.text
            or ""
        ).strip()

        if not self.text:
            raise ValidationError(
                {
                    "text": (
                        "Lyrics word text is required."
                    ),
                }
            )

        if self.end_ms <= self.start_ms:
            raise ValidationError(
                {
                    "end_ms": (
                        "Lyrics word end time must be "
                        "after its start time."
                    ),
                }
            )

        if self.confidence is not None:
            confidence = Decimal(
                self.confidence
            )

            if (
                confidence < Decimal("0")
                or confidence > Decimal("1")
            ):
                raise ValidationError(
                    {
                        "confidence": (
                            "Word confidence must be "
                            "between 0 and 1."
                        ),
                    }
                )

        if not self.line_id:
            return

        line = self.line

        if (
            line.start_ms is not None
            and self.start_ms < line.start_ms
        ):
            raise ValidationError(
                {
                    "start_ms": (
                        "Word timing cannot start "
                        "before its lyrics line."
                    ),
                }
            )

        if (
            line.end_ms is not None
            and self.end_ms > line.end_ms
        ):
            raise ValidationError(
                {
                    "end_ms": (
                        "Word timing cannot end "
                        "after its lyrics line."
                    ),
                }
            )

        track_duration_ms = (
            line
            .lyrics
            .track
            .duration_ms
        )

        if self.end_ms > track_duration_ms:
            raise ValidationError(
                {
                    "end_ms": (
                        "Word timing cannot exceed "
                        "track duration."
                    ),
                }
            )

    def save(
        self,
        *args,
        **kwargs,
    ):
        self.text = (
            self.text
            or ""
        ).strip()

        return super().save(
            *args,
            **kwargs,
        )

    def __str__(self) -> str:
        return (
            f"{self.line_id}:"
            f"{self.sequence} · "
            f"{self.text}"
        )

    class Meta:
        verbose_name = (
            "Music Lyrics Word"
        )
        verbose_name_plural = (
            "Music Lyrics Words"
        )

        ordering = (
            "sequence",
            "id",
        )

        indexes = [
            models.Index(
                fields=(
                    "line",
                    "sequence",
                ),
                name="audio_lyr_word_seq_idx",
            ),
            models.Index(
                fields=(
                    "line",
                    "start_ms",
                ),
                name="audio_lyr_word_start_idx",
            ),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=(
                    "line",
                    "sequence",
                ),
                name="audio_uniq_lyrics_word_seq",
            ),
            models.CheckConstraint(
                check=Q(
                    end_ms__gt=F(
                        "start_ms"
                    )
                ),
                name="audio_lyrics_word_timing_valid",
            ),
            models.CheckConstraint(
                check=(
                    Q(
                        confidence__isnull=True
                    )
                    | (
                        Q(
                            confidence__gte=0
                        )
                        & Q(
                            confidence__lte=1
                        )
                    )
                ),
                name="audio_lyrics_word_conf_valid",
            ),
        ]