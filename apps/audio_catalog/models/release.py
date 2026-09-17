# apps/audio_catalog/models/release.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-15.
# Last Update by Hossein Sakkaki on 2026-09-15.

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from utils.mixins.slug_mixin import SlugMixin

from .base import PublicIDTimestampedModel
from .contributors import TrackContributor


class MusicRelease(SlugMixin, PublicIDTimestampedModel):
    """
    Canonical TownLIT music release.

    Tracks remain the authority for playback and rights.
    """

    SLUG_ALLOW_UNICODE = True

    class ReleaseType(models.TextChoices):
        SINGLE = "single", "Single"
        EP = "ep", "EP"
        ALBUM = "album", "Album"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        REVIEW = "review", "Review"
        PUBLISHED = "published", "Published"
        SUSPENDED = "suspended", "Suspended"
        ARCHIVED = "archived", "Archived"

    catalog = models.ForeignKey(
        "audio_catalog.AudioCatalog",
        on_delete=models.PROTECT,
        related_name="releases",
    )

    title = models.CharField(max_length=180)
    subtitle = models.CharField(max_length=180, blank=True, default="")
    description = models.TextField(blank=True, default="")

    release_type = models.CharField(
        max_length=16,
        choices=ReleaseType.choices,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    language_code = models.CharField(max_length=16, blank=True, default="")
    release_date = models.DateField(null=True, blank=True, db_index=True)

    tracks = models.ManyToManyField(
        "audio_catalog.MusicTrack",
        through="audio_catalog.MusicReleaseTrack",
        related_name="releases",
    )
    contributors = models.ManyToManyField(
        "audio_catalog.AudioContributor",
        through="audio_catalog.MusicReleaseContributor",
        related_name="releases",
    )

    metadata = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1)

    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audio_releases_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audio_releases_updated",
    )

    def get_slug_source(self) -> str:
        title = (self.title or "").strip()
        subtitle = (self.subtitle or "").strip()
        return f"{title} {subtitle}" if subtitle else title

    def clean(self):
        super().clean()

        self.title = " ".join(str(self.title or "").split())
        self.subtitle = " ".join(str(self.subtitle or "").split())
        self.description = str(self.description or "").strip()

        if not self.title:
            raise ValidationError({"title": "Release title is required."})

        if self.status == self.Status.PUBLISHED:
            if not self.published_at:
                raise ValidationError(
                    {"published_at": "Published release requires published_at."}
                )
            if self.suspended_at or self.archived_at:
                raise ValidationError(
                    "Published release cannot have suspension or archive timestamps."
                )

        if self.status == self.Status.SUSPENDED and not self.suspended_at:
            raise ValidationError(
                {"suspended_at": "Suspended release requires suspended_at."}
            )

        if self.status == self.Status.ARCHIVED and not self.archived_at:
            raise ValidationError(
                {"archived_at": "Archived release requires archived_at."}
            )

    def save(self, *args, **kwargs):
        self.title = " ".join(str(self.title or "").split())
        self.subtitle = " ".join(str(self.subtitle or "").split())
        self.description = str(self.description or "").strip()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.title

    class Meta:
        verbose_name = "Music Release"
        verbose_name_plural = "Music Releases"
        ordering = ("-release_date", "-published_at", "title", "id")
        indexes = [
            models.Index(
                fields=("catalog", "status", "-release_date"),
                name="audio_release_catalog_idx",
            ),
            models.Index(
                fields=("release_type", "status"),
                name="audio_release_type_idx",
            ),
        ]


class MusicReleaseTrack(PublicIDTimestampedModel):
    release = models.ForeignKey(
        MusicRelease,
        on_delete=models.CASCADE,
        related_name="track_links",
    )
    track = models.ForeignKey(
        "audio_catalog.MusicTrack",
        on_delete=models.PROTECT,
        related_name="release_links",
    )

    disc_number = models.PositiveSmallIntegerField(default=1)
    track_number = models.PositiveSmallIntegerField()

    def clean(self):
        super().clean()

        if self.disc_number < 1:
            raise ValidationError({"disc_number": "Disc number must be at least 1."})

        if self.track_number < 1:
            raise ValidationError({"track_number": "Track number must be at least 1."})

        if (
            self.release_id
            and self.track_id
            and self.release.catalog_id != self.track.catalog_id
        ):
            raise ValidationError(
                {"track": "Release track must belong to the same Audio Catalog."}
            )

    def __str__(self) -> str:
        return (
            f"{self.release.title} · "
            f"{self.disc_number}.{self.track_number} · "
            f"{self.track.title}"
        )

    class Meta:
        verbose_name = "Music Release Track"
        verbose_name_plural = "Music Release Tracks"
        ordering = ("disc_number", "track_number", "id")
        constraints = [
            models.CheckConstraint(
                check=Q(disc_number__gte=1),
                name="audio_release_disc_number_gte_one",
            ),
            models.CheckConstraint(
                check=Q(track_number__gte=1),
                name="audio_release_track_number_gte_one",
            ),
            models.UniqueConstraint(
                fields=("release", "track"),
                name="audio_unique_release_track",
            ),
            models.UniqueConstraint(
                fields=("release", "disc_number", "track_number"),
                name="audio_unique_release_track_position",
            ),
        ]
        indexes = [
            models.Index(
                fields=("release", "disc_number", "track_number"),
                name="audio_release_track_order_idx",
            ),
            models.Index(
                fields=("track", "release"),
                name="audio_track_release_idx",
            ),
        ]


class MusicReleaseContributor(PublicIDTimestampedModel):
    release = models.ForeignKey(
        MusicRelease,
        on_delete=models.CASCADE,
        related_name="contributor_links",
    )
    contributor = models.ForeignKey(
        "audio_catalog.AudioContributor",
        on_delete=models.PROTECT,
        related_name="release_links",
    )

    role = models.CharField(
        max_length=40,
        choices=TrackContributor.Role.choices,
        db_index=True,
    )
    credit_text = models.CharField(max_length=255, blank=True, default="")
    sort_order = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return (
            f"{self.release.title} · "
            f"{self.contributor.display_name} · "
            f"{self.role}"
        )

    class Meta:
        verbose_name = "Music Release Contributor"
        verbose_name_plural = "Music Release Contributors"
        ordering = ("sort_order", "role", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("release", "contributor", "role"),
                name="audio_unique_release_contributor_role",
            ),
        ]
        indexes = [
            models.Index(
                fields=("release", "role", "sort_order"),
                name="audio_release_contrib_idx",
            ),
        ]