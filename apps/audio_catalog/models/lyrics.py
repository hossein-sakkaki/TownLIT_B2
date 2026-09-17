# apps/audio_catalog/models/lyrics.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-14.
# Last Update by Hossein Sakkaki on 2026-09-14.

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from .base import PublicIDTimestampedModel


class MusicLyrics(PublicIDTimestampedModel):
    """
    Canonical lyrics document for one music track.

    V1 supports plain and line-synchronized lyrics. Lines remain separate
    records so a future word/segment layer can attach to them without
    redesigning the document model.
    """

    class Kind(models.TextChoices):
        ORIGINAL = "original", "Original"
        TRANSLATION = "translation", "Translation"
        TRANSLITERATION = "transliteration", "Transliteration"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        REVIEW = "review", "Review"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    class TimingMode(models.TextChoices):
        PLAIN = "plain", "Plain"
        LINE = "line", "Line synchronized"

    track = models.ForeignKey(
        "audio_catalog.MusicTrack",
        on_delete=models.CASCADE,
        related_name="lyrics_documents",
    )

    reference_variant = models.ForeignKey(
        "audio_catalog.MusicTrackVariant",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="lyrics_documents",
        help_text=(
            "Optional canonical audio variant used while authoring timing. "
            "The lyrics still belong to the track."
        ),
    )

    rights_record = models.ForeignKey(
        "audio_catalog.MusicRightsRecord",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="lyrics_documents",
        help_text=(
            "Optional existing track rights record associated with this "
            "lyrics document. No additional lyrics-display right is inferred."
        ),
    )

    language_code = models.CharField(
        max_length=16,
        blank=True,
        default="",
        db_index=True,
    )

    kind = models.CharField(
        max_length=20,
        choices=Kind.choices,
        default=Kind.ORIGINAL,
        db_index=True,
    )

    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    timing_mode = models.CharField(
        max_length=12,
        choices=TimingMode.choices,
        default=TimingMode.PLAIN,
        db_index=True,
    )

    # Positive values delay all cues relative to playback.
    timing_offset_ms = models.IntegerField(
        default=0,
    )

    is_default = models.BooleanField(
        default=False,
        db_index=True,
    )

    # MySQL-safe nullable uniqueness slot for the default document.
    default_slot = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        editable=False,
    )

    plain_text = models.TextField(
        blank=True,
        default="",
        help_text=(
            "Plain lyrics fallback. For synchronized lyrics, line records "
            "are the canonical timed representation."
        ),
    )

    source_label = models.CharField(
        max_length=180,
        blank=True,
        default="",
    )

    source_url = models.URLField(
        max_length=500,
        blank=True,
        default="",
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    published_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )

    def _sync_default_slot(self) -> bool:
        expected = 1 if self.is_default else None
        changed = self.default_slot != expected
        self.default_slot = expected
        return changed

    def clean(self) -> None:
        super().clean()

        self.language_code = self.normalize_language_code(
            self.language_code
        )
        self.plain_text = (self.plain_text or "").strip()
        self.source_label = (self.source_label or "").strip()
        self.source_url = (self.source_url or "").strip()
        self._sync_default_slot()

        if (
            self.reference_variant_id
            and self.track_id
            and self.reference_variant.track_id != self.track_id
        ):
            raise ValidationError(
                {
                    "reference_variant": (
                        "Reference variant must belong to the same track."
                    ),
                }
            )

        if (
            self.rights_record_id
            and self.track_id
            and self.rights_record.track_id != self.track_id
        ):
            raise ValidationError(
                {
                    "rights_record": (
                        "Lyrics rights record must belong to the same track."
                    ),
                }
            )

    def save(self, *args, **kwargs):
        self.language_code = self.normalize_language_code(
            self.language_code
        )
        self.plain_text = (self.plain_text or "").strip()
        self.source_label = (self.source_label or "").strip()
        self.source_url = (self.source_url or "").strip()

        slot_changed = self._sync_default_slot()

        update_fields = kwargs.get("update_fields")
        if slot_changed and update_fields is not None:
            update_fields = list(
                dict.fromkeys(
                    [
                        *update_fields,
                        "default_slot",
                    ]
                )
            )
            kwargs["update_fields"] = update_fields

        if (
            self.status == self.Status.PUBLISHED
            and self.published_at is None
        ):
            self.published_at = timezone.now()

            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = list(
                    dict.fromkeys(
                        [
                            *update_fields,
                            "published_at",
                        ]
                    )
                )

        return super().save(*args, **kwargs)

    @staticmethod
    def normalize_language_code(value: str | None) -> str:
        return (
            str(value or "")
            .strip()
            .replace("_", "-")
            .lower()
        )[:16]

    def __str__(self) -> str:
        language = self.language_code or "und"
        return f"{self.track.title} · {language} · {self.kind}"

    class Meta:
        verbose_name = "Music Lyrics"
        verbose_name_plural = "Music Lyrics"

        ordering = (
            "track_id",
            "-is_default",
            "language_code",
            "kind",
            "id",
        )

        indexes = [
            models.Index(
                fields=(
                    "track",
                    "status",
                    "language_code",
                ),
                name="audio_lyr_track_status_lang",
            ),
            models.Index(
                fields=(
                    "status",
                    "is_default",
                ),
                name="audio_lyr_status_default",
            ),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=(
                    "track",
                    "language_code",
                    "kind",
                ),
                name="audio_uniq_track_lyr_lang_kind",
            ),
            models.UniqueConstraint(
                fields=(
                    "track",
                    "default_slot",
                ),
                name="audio_uniq_default_lyrics",
            ),
        ]


class MusicLyricsLine(PublicIDTimestampedModel):
    """
    One ordered lyrics line with optional millisecond timing.

    Future word/segment synchronization should reference this line instead
    of replacing it, keeping line-level clients backward compatible.
    """

    lyrics = models.ForeignKey(
        "audio_catalog.MusicLyrics",
        on_delete=models.CASCADE,
        related_name="lines",
    )

    sequence = models.PositiveIntegerField()

    text = models.TextField()

    start_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    end_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    def clean(self) -> None:
        super().clean()

        self.text = (self.text or "").strip()

        if not self.text:
            raise ValidationError(
                {
                    "text": "Lyrics line text is required.",
                }
            )

        if self.end_ms is not None and self.start_ms is None:
            raise ValidationError(
                {
                    "end_ms": (
                        "Lyrics line end time requires a start time."
                    ),
                }
            )

        if (
            self.start_ms is not None
            and self.end_ms is not None
            and self.end_ms <= self.start_ms
        ):
            raise ValidationError(
                {
                    "end_ms": (
                        "Lyrics line end time must be after its start time."
                    ),
                }
            )

        if not self.lyrics_id:
            return

        if (
            self.lyrics.timing_mode
            == MusicLyrics.TimingMode.LINE
            and self.start_ms is None
        ):
            raise ValidationError(
                {
                    "start_ms": (
                        "Line-synchronized lyrics require a start time "
                        "for every line."
                    ),
                }
            )

        if (
            self.lyrics.timing_mode
            == MusicLyrics.TimingMode.PLAIN
            and (
                self.start_ms is not None
                or self.end_ms is not None
            )
        ):
            raise ValidationError(
                {
                    "start_ms": (
                        "Plain lyrics cannot contain synchronized timing."
                    ),
                }
            )

        duration_ms = self.lyrics.track.duration_ms

        if (
            self.start_ms is not None
            and self.start_ms > duration_ms
        ):
            raise ValidationError(
                {
                    "start_ms": (
                        "Lyrics line start time cannot exceed track duration."
                    ),
                }
            )

        if (
            self.end_ms is not None
            and self.end_ms > duration_ms
        ):
            raise ValidationError(
                {
                    "end_ms": (
                        "Lyrics line end time cannot exceed track duration."
                    ),
                }
            )

    def save(self, *args, **kwargs):
        self.text = (self.text or "").strip()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.lyrics_id}:{self.sequence} · {self.text[:60]}"

    class Meta:
        verbose_name = "Music Lyrics Line"
        verbose_name_plural = "Music Lyrics Lines"

        ordering = (
            "sequence",
            "id",
        )

        indexes = [
            models.Index(
                fields=(
                    "lyrics",
                    "sequence",
                ),
                name="audio_lyr_line_seq_idx",
            ),
            models.Index(
                fields=(
                    "lyrics",
                    "start_ms",
                ),
                name="audio_lyr_line_start_idx",
            ),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=(
                    "lyrics",
                    "sequence",
                ),
                name="audio_uniq_lyrics_line_seq",
            ),
            models.CheckConstraint(
                check=(
                    Q(
                        start_ms__isnull=True,
                        end_ms__isnull=True,
                    )
                    | Q(
                        start_ms__isnull=False,
                        end_ms__isnull=True,
                    )
                    | Q(
                        start_ms__isnull=False,
                        end_ms__gt=F("start_ms"),
                    )
                ),
                name="audio_lyrics_line_timing_valid",
            ),
        ]
