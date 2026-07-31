# apps/audio_catalog/models/track.py

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q

from utils.mixins.slug_mixin import SlugMixin

from .base import PublicIDTimestampedModel


class MusicTrack(
    SlugMixin,
    PublicIDTimestampedModel,
):
    """
    Canonical music track in the TownLIT audio catalog.
    """

    SLUG_ALLOW_UNICODE = True

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        REVIEW = "review", "Review"
        PUBLISHED = "published", "Published"
        SUSPENDED = "suspended", "Suspended"
        ARCHIVED = "archived", "Archived"

    class SourceType(models.TextChoices):
        TOWNLIT_AI_ASSISTED = (
            "townlit_ai_assisted",
            "TownLIT AI-assisted",
        )
        TOWNLIT_ORIGINAL = (
            "townlit_original",
            "TownLIT Original",
        )
        ARTIST_LICENSED = (
            "artist_licensed",
            "Artist Licensed",
        )
        PROVIDER_LICENSED = (
            "provider_licensed",
            "Provider Licensed",
        )
        PUBLIC_DOMAIN = (
            "public_domain",
            "Public Domain",
        )
        OTHER = (
            "other",
            "Other",
        )

    # -------------------------------------------------
    # Catalog and identity
    # -------------------------------------------------
    catalog = models.ForeignKey(
        "audio_catalog.AudioCatalog",
        on_delete=models.PROTECT,
        related_name="tracks",
    )

    title = models.CharField(
        max_length=180,
    )

    subtitle = models.CharField(
        max_length=180,
        blank=True,
        default="",
    )

    description = models.TextField(
        blank=True,
        default="",
    )

    source_type = models.CharField(
        max_length=32,
        choices=SourceType.choices,
        default=SourceType.TOWNLIT_AI_ASSISTED,
        db_index=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    # -------------------------------------------------
    # Taxonomy
    # -------------------------------------------------
    categories = models.ManyToManyField(
        "audio_catalog.AudioCategory",
        related_name="tracks",
        blank=True,
    )

    genres = models.ManyToManyField(
        "audio_catalog.AudioGenre",
        related_name="tracks",
        blank=True,
    )

    moods = models.ManyToManyField(
        "audio_catalog.AudioMood",
        related_name="tracks",
        blank=True,
    )

    tags = models.ManyToManyField(
        "audio_catalog.AudioTag",
        related_name="tracks",
        blank=True,
    )

    # -------------------------------------------------
    # Music metadata
    # -------------------------------------------------
    duration_ms = models.PositiveIntegerField(
        default=1,
    )

    bpm = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )

    musical_key = models.CharField(
        max_length=16,
        blank=True,
        default="",
    )

    time_signature = models.CharField(
        max_length=16,
        blank=True,
        default="",
    )

    language_code = models.CharField(
        max_length=16,
        blank=True,
        default="",
    )

    is_instrumental = models.BooleanField(
        default=True,
        db_index=True,
    )

    has_vocals = models.BooleanField(
        default=False,
    )

    is_explicit = models.BooleanField(
        default=False,
        db_index=True,
    )

    is_ai_assisted = models.BooleanField(
        default=False,
        db_index=True,
    )

    is_test_asset = models.BooleanField(
        default=False,
        db_index=True,
    )

    # -------------------------------------------------
    # Usage policy
    # -------------------------------------------------
    allow_ugc = models.BooleanField(
        default=True,
    )

    allow_streaming = models.BooleanField(
        default=True,
    )

    allow_standalone_download = models.BooleanField(
        default=False,
    )

    allow_external_export = models.BooleanField(
        default=False,
    )

    allow_commercial_accounts = models.BooleanField(
        default=True,
    )

    min_clip_duration_ms = models.PositiveIntegerField(
        default=5000,
    )

    max_clip_duration_ms = models.PositiveIntegerField(
        default=60000,
    )

    # -------------------------------------------------
    # Search and ranking
    # -------------------------------------------------
    search_document = models.TextField(
        blank=True,
        default="",
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    version = models.PositiveIntegerField(
        default=1,
    )

    sort_order = models.PositiveIntegerField(
        default=0,
    )

    popularity_score = models.PositiveBigIntegerField(
        default=0,
    )

    # -------------------------------------------------
    # Publishing lifecycle
    # -------------------------------------------------
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )

    suspended_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    archived_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # -------------------------------------------------
    # Audit
    # -------------------------------------------------
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audio_tracks_created",
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audio_tracks_updated",
    )

    # -------------------------------------------------
    # Slug
    # -------------------------------------------------
    def get_slug_source(self) -> str:
        """
        Build a stable slug from title and subtitle.
        """

        title = (self.title or "").strip()
        subtitle = (self.subtitle or "").strip()

        if subtitle:
            return f"{title} {subtitle}"

        return title

    def __str__(self) -> str:
        return self.title

    class Meta:
        verbose_name = "Music Track"
        verbose_name_plural = "Music Tracks"

        ordering = (
            "sort_order",
            "-published_at",
            "title",
            "id",
        )

        indexes = [
            models.Index(
                fields=(
                    "catalog",
                    "status",
                    "sort_order",
                )
            ),
            models.Index(
                fields=(
                    "status",
                    "is_test_asset",
                    "published_at",
                )
            ),
            models.Index(
                fields=(
                    "is_instrumental",
                    "is_explicit",
                    "status",
                )
            ),
            models.Index(
                fields=(
                    "source_type",
                    "status",
                )
            ),
            models.Index(
                fields=(
                    "popularity_score",
                    "published_at",
                )
            ),
        ]

        constraints = [
            models.CheckConstraint(
                check=Q(
                    duration_ms__gt=0,
                ),
                name="audio_track_duration_gt_zero",
            ),
            models.CheckConstraint(
                check=Q(
                    max_clip_duration_ms__gte=models.F(
                        "min_clip_duration_ms"
                    )
                ),
                name="audio_track_clip_range_valid",
            ),
            models.CheckConstraint(
                check=(
                    Q(
                        is_instrumental=False,
                    )
                    | Q(
                        has_vocals=False,
                    )
                ),
                name="audio_instrumental_without_vocals",
            ),
        ]