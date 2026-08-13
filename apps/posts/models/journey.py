# apps/posts/models/journey.py

from __future__ import annotations

from datetime import timedelta

from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.audio_catalog.models import MusicTrack, MusicTrackVariant
from apps.core.availability.interfaces import AvailabilityAware
from apps.core.boundaries.services.policy import BoundaryPolicy
from apps.core.interactions.models import ReactionBreakdownMixin
from apps.core.moderation.mixins import ModerationTargetMixin
from apps.core.ownership.owner_resolver import resolve_owner_user_and_member
from apps.core.visibility.mixins import VisibilityModelMixin
from apps.core.visibility.policy import VisibilityPolicy
from apps.creative_editor.models import CreativeComposition, CreativeRenderJob
from apps.posts.constants.journeys import (
    JOURNEY_ACTIVE_DURATION_HOURS,
    JOURNEY_DEFAULT_DURATION_MS,
    JOURNEY_MAX_DURATION_MS,
    JOURNEY_MAX_ENTRIES_PER_DAY,
    JOURNEY_MIN_DURATION_MS,
    JourneyEntryMediaType,
    JourneyPaletteMode,
    JourneyRetentionPolicy,
    JourneyViewSource,
    JourneyVisualSourceType,
)
from utils.common.utils import FileUpload
from utils.mixins.media_assets import MediaAssetsMixin
from utils.mixins.slug_mixin import SlugMixin
from validators.security_validators import (
    validate_no_executable_file,
)


class Journey(SlugMixin, models.Model):
    """
    One local-day Journey chapter.
    """

    id = models.BigAutoField(primary_key=True)

    # -------------------------------------------------
    # Polymorphic owner
    # -------------------------------------------------
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="journey_chapters",
    )
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    # -------------------------------------------------
    # Local-day identity
    # -------------------------------------------------
    local_date = models.DateField(db_index=True)
    timezone_name = models.CharField(max_length=64, default="UTC")
    palette_mode = models.CharField(
        max_length=16,
        choices=JourneyPaletteMode.choices,
        db_index=True,
    )
    display_seed = models.PositiveIntegerField(default=0)

    # -------------------------------------------------
    # Journey Close
    # -------------------------------------------------
    close_text = models.TextField(blank=True, default="")
    close_is_private = models.BooleanField(default=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    # -------------------------------------------------
    # Lifecycle
    # -------------------------------------------------
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    url_name = "posts:journey-detail"

    def get_slug_source(self) -> str:
        return f"journey-{self.object_id}-{self.local_date.isoformat()}"

    def clean(self):
        super().clean()

        if not self.content_type_id or not self.object_id:
            raise ValidationError("Journey owner is required.")

    @property
    def entry_count(self) -> int:
        prefetched = getattr(self, "_prefetched_objects_cache", {})

        if "entries" in prefetched:
            return len(
                [item for item in prefetched["entries"] if item.is_active]
            )

        return self.entries.filter(is_active=True).count()

    @property
    def remaining_capacity(self) -> int:
        return max(JOURNEY_MAX_ENTRIES_PER_DAY - self.entry_count, 0)

    @property
    def max_entries(self) -> int:
        return JOURNEY_MAX_ENTRIES_PER_DAY

    @property
    def owner_user(self):
        owner_user, _, _ = resolve_owner_user_and_member(self)
        return owner_user

    def can_close(self) -> bool:
        return bool(self.entry_count > 0 and not self.closed_at)

    def close(self, *, text: str, is_private: bool = True) -> None:
        clean_text = str(text or "").strip()

        if not clean_text:
            raise ValidationError(
                {"close_text": "Journey Close text is required."}
            )

        if len(clean_text) > 2_000:
            raise ValidationError(
                {
                    "close_text": (
                        "Journey Close cannot exceed 2000 characters."
                    ),
                }
            )

        self.close_text = clean_text
        self.close_is_private = bool(is_private)
        self.closed_at = timezone.now()

        self.save(
            update_fields=[
                "close_text",
                "close_is_private",
                "closed_at",
                "updated_at",
            ]
        )

    def __str__(self) -> str:
        return f"Journey #{self.pk} · {self.local_date}"

    class Meta:
        verbose_name = "Journey"
        verbose_name_plural = "Journeys"
        ordering = ("-local_date", "-id")

        indexes = [
            models.Index(
                fields=("content_type", "object_id", "-local_date"),
                name="journey_owner_day_idx",
            ),
            models.Index(
                fields=("local_date", "palette_mode"),
                name="journey_day_palette_idx",
            ),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=("content_type", "object_id", "local_date"),
                name="journey_unique_owner_local_day",
            ),
        ]


class JourneyEntry(
    ModerationTargetMixin,
    VisibilityModelMixin,
    ReactionBreakdownMixin,
    MediaAssetsMixin,
    SlugMixin,
    AvailabilityAware,
    models.Model,
):
    """
    One immutable published Journey entry.
    """

    IMAGE = FileUpload("posts", "images", "journey")
    VIDEO = FileUpload("posts", "videos", "journey")
    THUMBNAIL = FileUpload("posts", "thumbnails", "journey")

    id = models.BigAutoField(primary_key=True)

    journey = models.ForeignKey(
        Journey,
        on_delete=models.CASCADE,
        related_name="entries",
    )

    # -------------------------------------------------
    # Owner snapshot
    # -------------------------------------------------
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="journey_entries",
    )
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    # -------------------------------------------------
    # Generic interactions
    # -------------------------------------------------
    reactions = GenericRelation(
        "posts.Reaction",
        content_type_field="content_type",
        object_id_field="object_id",
        related_query_name="journey_entry_targets",
    )

    # -------------------------------------------------
    # Immutable sequence
    # -------------------------------------------------
    sequence = models.PositiveSmallIntegerField(db_index=True)

    # -------------------------------------------------
    # Future-ready media identity
    # -------------------------------------------------
    media_type = models.CharField(
        max_length=24,
        choices=JourneyEntryMediaType.choices,
        default=JourneyEntryMediaType.IMAGE,
        db_index=True,
    )
    visual_source_type = models.CharField(
        max_length=32,
        choices=JourneyVisualSourceType.choices,
        db_index=True,
    )

    # -------------------------------------------------
    # Creative Editor audit
    # -------------------------------------------------
    composition = models.ForeignKey(
        CreativeComposition,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="published_journey_entries",
    )
    render_job = models.ForeignKey(
        CreativeRenderJob,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="published_journey_entries",
    )
    composition_public_id_snapshot = models.UUIDField()
    render_job_public_id_snapshot = models.UUIDField()
    composition_revision = models.PositiveIntegerField()
    composition_document_sha256 = models.CharField(
        max_length=64,
        db_index=True,
    )

    # -------------------------------------------------
    # Immutable published assets
    # -------------------------------------------------
    rendered_image = models.ImageField(
        upload_to=IMAGE.dir_upload,
        max_length=700,
        null=True,
        blank=True,
        validators=[],
    )

    rendered_video = models.FileField(
        upload_to=VIDEO.dir_upload,
        max_length=700,
        null=True,
        blank=True,
        validators=[
            validate_no_executable_file,
        ],
    )
    thumbnail = models.ImageField(
        upload_to=THUMBNAIL.dir_upload,
        max_length=700,
        validators=[],
    )

    # -------------------------------------------------
    # Music reference
    # -------------------------------------------------
    music_track = models.ForeignKey(
        MusicTrack,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="journey_entries",
    )
    music_variant = models.ForeignKey(
        MusicTrackVariant,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="journey_entries",
    )
    music_clip_start_ms = models.PositiveIntegerField(null=True, blank=True)
    music_clip_end_ms = models.PositiveIntegerField(null=True, blank=True)
    music_volume = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        default=1,
    )
    music_attribution_text = models.TextField(blank=True, default="")

    # -------------------------------------------------
    # Display timing
    # -------------------------------------------------
    display_duration_ms = models.PositiveIntegerField(
        default=JOURNEY_DEFAULT_DURATION_MS,
    )

    # -------------------------------------------------
    # Retention lifecycle
    # -------------------------------------------------
    retention_policy = models.CharField(
        max_length=32,
        choices=JourneyRetentionPolicy.choices,
        default=JourneyRetentionPolicy.KEEP,
        db_index=True,
    )
    published_at = models.DateTimeField(default=timezone.now, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    archived_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # -------------------------------------------------
    # Analytics
    # -------------------------------------------------
    view_count_internal = models.PositiveBigIntegerField(default=0)
    unique_viewers_count = models.PositiveBigIntegerField(default=0)
    reactions_count = models.PositiveIntegerField(default=0)
    last_viewed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    url_name = "posts:journey-entry-detail"

    def get_slug_source(self) -> str:
        timestamp = self.published_at.strftime("%Y%m%d%H%M%S")
        return f"journey-entry-{timestamp}-{self.sequence}"

    def clean(self):
        super().clean()

        if self.media_type == JourneyEntryMediaType.IMAGE:
            if not self.rendered_image:
                raise ValidationError(
                    {
                        "rendered_image": (
                            "Image Journey requires a rendered image."
                        ),
                    }
                )

            if self.rendered_video:
                raise ValidationError(
                    {
                        "rendered_video": (
                            "Image Journey cannot contain a rendered video."
                        ),
                    }
                )

        elif self.media_type == JourneyEntryMediaType.VIDEO:
            if not self.rendered_video:
                raise ValidationError(
                    {
                        "rendered_video": (
                            "Video Journey requires a rendered video."
                        ),
                    }
                )

            if self.rendered_image:
                raise ValidationError(
                    {
                        "rendered_image": (
                            "Video Journey cannot contain a rendered image."
                        ),
                    }
                )

        else:
            raise ValidationError(
                {
                    "media_type": (
                        "Unsupported Journey media type."
                    ),
                }
            )

        if not self.thumbnail:
            raise ValidationError(
                {"thumbnail": "Journey requires a thumbnail."}
            )

        if self.sequence < 1:
            raise ValidationError(
                {"sequence": "Journey sequence must start at 1."}
            )

        if self.sequence > JOURNEY_MAX_ENTRIES_PER_DAY:
            raise ValidationError(
                {
                    "sequence": (
                        "Journey daily entry limit was exceeded."
                    ),
                }
            )

        if (
            self.content_type_id != self.journey.content_type_id
            or self.object_id != self.journey.object_id
        ):
            raise ValidationError(
                "Journey entry owner does not match its Journey."
            )

        self._validate_display_duration()
        self._validate_music_fields()

    def _validate_display_duration(self):
        if (
            self.display_duration_ms < JOURNEY_MIN_DURATION_MS
            or self.display_duration_ms > JOURNEY_MAX_DURATION_MS
        ):
            raise ValidationError(
                {
                    "display_duration_ms": (
                        "Journey duration must be between 15 and 60 seconds."
                    ),
                }
            )

    def _validate_music_fields(self):
        has_track = bool(self.music_track_id)
        has_variant = bool(self.music_variant_id)
        has_start = self.music_clip_start_ms is not None
        has_end = self.music_clip_end_ms is not None

        values_present = any([has_track, has_variant, has_start, has_end])
        values_complete = all([has_track, has_variant, has_start, has_end])

        if values_present and not values_complete:
            raise ValidationError(
                "Journey music fields must be provided together."
            )

        if not values_present:
            return

        if self.music_variant.track_id != self.music_track_id:
            raise ValidationError(
                {
                    "music_variant": (
                        "Music variant does not belong to the selected track."
                    ),
                }
            )

        if self.music_clip_end_ms <= self.music_clip_start_ms:
            raise ValidationError(
                {
                    "music_clip_end_ms": (
                        "Music clip end must be greater than its start."
                    ),
                }
            )

        clip_duration = self.music_clip_end_ms - self.music_clip_start_ms

        if clip_duration != self.display_duration_ms:
            raise ValidationError(
                {
                    "display_duration_ms": (
                        "Display duration must match the selected music clip."
                    ),
                }
            )

    @property
    def owner_user(self):
        owner_user, _, _ = resolve_owner_user_and_member(self)
        return owner_user

    @property
    def is_live(self) -> bool:
        now = timezone.now()

        return bool(
            self.is_available()
            and self.published_at <= now
            and self.expires_at > now
            and self.archived_at is None
        )

    @property
    def is_archived(self) -> bool:
        return bool(self.archived_at is not None)

    @property
    def has_music(self) -> bool:
        return bool(self.music_track_id and self.music_variant_id)

    def is_available(self) -> bool:
        has_rendered_media = (
            bool(self.rendered_video)
            if self.media_type == JourneyEntryMediaType.VIDEO
            else bool(self.rendered_image)
        )

        return bool(
            self.is_active
            and not self.is_hidden
            and not self.is_suspended
            and has_rendered_media
            and self.thumbnail
        )

    def on_available(self):
        """
        Journey publication does not create a public notification.
        """

        return

    def archive(self, *, at=None) -> None:
        if self.archived_at:
            return

        now = at or timezone.now()

        type(self).objects.filter(
            pk=self.pk,
            archived_at__isnull=True,
        ).update(
            archived_at=now,
            updated_at=now,
        )

        self.archived_at = now

    def can_deliver_asset(
        self,
        *,
        viewer,
        field_name: str,
        intent: str,
    ) -> bool:
        """
        Authorize immutable Journey assets.
        """

        if field_name not in {
            "rendered_image",
            "rendered_video",
            "thumbnail",
        }:
            return False

        field = getattr(self, field_name, None)

        if not field:
            return False

        if not self.is_available():
            return False

        is_authenticated = bool(
            viewer and getattr(viewer, "is_authenticated", False)
        )

        if is_authenticated and getattr(viewer, "is_staff", False):
            return True

        owner_user = self.owner_user

        if (
            is_authenticated
            and owner_user
            and viewer.pk == owner_user.pk
        ):
            return True

        if (
            is_authenticated
            and owner_user
            and BoundaryPolicy.has_boundary_between(viewer, owner_user)
        ):
            return False

        return VisibilityPolicy.can_view(viewer=viewer, obj=self)

    def __str__(self) -> str:
        return (
            f"Journey Entry #{self.pk} · "
            f"{self.journey.local_date} · "
            f"{self.sequence}"
        )

    class Meta:
        verbose_name = "Journey Entry"
        verbose_name_plural = "Journey Entries"
        ordering = ("sequence", "id")

        indexes = [
            models.Index(
                fields=("journey", "sequence"),
                name="journey_entry_order_idx",
            ),
            models.Index(
                fields=("content_type", "object_id", "-published_at"),
                name="journey_entry_owner_pub_idx",
            ),
            models.Index(
                fields=("expires_at", "retention_policy", "archived_at"),
                name="journey_entry_expiry_idx",
            ),
            models.Index(
                fields=(
                    "visibility",
                    "is_active",
                    "is_hidden",
                    "-published_at",
                ),
                name="journey_entry_visible_idx",
            ),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=("journey", "sequence"),
                name="journey_unique_entry_sequence",
            ),
            models.CheckConstraint(
                check=Q(sequence__gte=1)
                & Q(sequence__lte=JOURNEY_MAX_ENTRIES_PER_DAY),
                name="journey_entry_sequence_range",
            ),
            models.CheckConstraint(
                check=Q(display_duration_ms__gte=JOURNEY_MIN_DURATION_MS)
                & Q(display_duration_ms__lte=JOURNEY_MAX_DURATION_MS),
                name="journey_entry_duration_range",
            ),
            models.CheckConstraint(
                check=Q(expires_at__gt=models.F("published_at")),
                name="journey_entry_expiry_after_publish",
            ),
            models.UniqueConstraint(
                fields=(
                    "composition_public_id_snapshot",
                    "composition_revision",
                ),
                name="journey_unique_composition_revision",
            ),
        ]


class JourneyEntryView(models.Model):
    """
    Private viewer analytics for one Journey entry.
    """

    id = models.BigAutoField(primary_key=True)

    entry = models.ForeignKey(
        JourneyEntry,
        on_delete=models.CASCADE,
        related_name="viewer_records",
    )
    viewer = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.CASCADE,
        related_name="journey_entry_views",
    )

    first_viewed_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )
    last_viewed_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )
    view_count = models.PositiveIntegerField(default=1)
    max_progress_ms = models.PositiveIntegerField(default=0)
    completed = models.BooleanField(default=False, db_index=True)
    source = models.CharField(
        max_length=32,
        choices=JourneyViewSource.choices,
        default=JourneyViewSource.OTHER,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Journey Entry View"
        verbose_name_plural = "Journey Entry Views"
        ordering = ("-last_viewed_at", "-id")

        constraints = [
            models.UniqueConstraint(
                fields=("entry", "viewer"),
                name="journey_unique_entry_viewer",
            ),
        ]

        indexes = [
            models.Index(
                fields=("entry", "-last_viewed_at"),
                name="journey_view_entry_time_idx",
            ),
            models.Index(
                fields=("viewer", "-last_viewed_at"),
                name="journey_view_user_time_idx",
            ),
            models.Index(
                fields=("entry", "completed"),
                name="journey_view_completion_idx",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"Journey View · "
            f"{self.entry_id} · "
            f"{self.viewer_id}"
        )