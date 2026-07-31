# apps/audio_catalog/models/analytics.py

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class PlaybackSurface(models.TextChoices):
    AUDIO_LIBRARY = "audio_library", "Audio Library"
    SEARCH = "search", "Search"
    TRENDING = "trending", "Trending"
    RECOMMENDED = "recommended", "Recommended"
    RECENT = "recent", "Recent"
    FAVORITES = "favorites", "Favorites"
    CONTENT_CREATION = "content_creation", "Content Creation"
    MOMENT = "moment", "Moment"
    TESTIMONY = "testimony", "Testimony"
    
    # Journey playback.
    JOURNEY = "journey", "Journey"
    
    PROFILE = "profile", "Profile"
    DEEP_LINK = "deep_link", "Deep Link"
    OTHER = "other", "Other"


class PlaybackEndReason(models.TextChoices):
    COMPLETED = "completed", "Completed"
    PAUSED = "paused", "Paused"
    SWITCHED_TRACK = "switched_track", "Switched Track"
    DISMISSED = "dismissed", "Dismissed"
    BACKGROUNDED = "backgrounded", "Backgrounded"
    ERROR = "error", "Error"
    USED_IN_CONTENT = "used_in_content", "Used in Content"
    STALE = "stale", "Stale"


class AudioPlaybackSession(models.Model):
    """
    One logical user playback session.

    Raw sessions are retained temporarily. Aggregates are retained long-term.
    """

    id = models.BigAutoField(
        primary_key=True,
    )

    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    session_id = models.UUIDField(
        unique=True,
        db_index=True,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audio_playback_sessions",
    )

    track = models.ForeignKey(
        "audio_catalog.MusicTrack",
        on_delete=models.CASCADE,
        related_name="playback_sessions",
    )

    variant = models.ForeignKey(
        "audio_catalog.MusicTrackVariant",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="playback_sessions",
    )

    surface = models.CharField(
        max_length=32,
        choices=PlaybackSurface.choices,
        default=PlaybackSurface.OTHER,
        db_index=True,
    )

    source_context = models.JSONField(
        default=dict,
        blank=True,
    )

    client_platform = models.CharField(
        max_length=24,
        blank=True,
        default="",
        db_index=True,
    )

    client_version = models.CharField(
        max_length=40,
        blank=True,
        default="",
    )

    device_id_hash = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
    )

    duration_ms_snapshot = models.PositiveIntegerField(
        default=1,
    )

    max_position_ms = models.PositiveIntegerField(
        default=0,
    )

    listened_ms = models.PositiveBigIntegerField(
        default=0,
    )

    last_sequence = models.PositiveIntegerField(
        default=0,
    )

    play_counted = models.BooleanField(
        default=False,
    )

    qualified_play = models.BooleanField(
        default=False,
        db_index=True,
    )

    completed = models.BooleanField(
        default=False,
        db_index=True,
    )

    early_skipped = models.BooleanField(
        default=False,
        db_index=True,
    )

    used_in_content = models.BooleanField(
        default=False,
    )

    is_test_session = models.BooleanField(
        default=False,
        db_index=True,
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )

    end_reason = models.CharField(
        max_length=24,
        choices=PlaybackEndReason.choices,
        blank=True,
        default="",
        db_index=True,
    )

    started_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )

    last_heartbeat_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )

    ended_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = "Audio Playback Session"
        verbose_name_plural = "Audio Playback Sessions"

        ordering = [
            "-started_at",
            "-id",
        ]

        indexes = [
            models.Index(
                fields=[
                    "track",
                    "started_at",
                ]
            ),
            models.Index(
                fields=[
                    "user",
                    "started_at",
                ]
            ),
            models.Index(
                fields=[
                    "track",
                    "qualified_play",
                    "started_at",
                ]
            ),
            models.Index(
                fields=[
                    "track",
                    "completed",
                    "started_at",
                ]
            ),
            models.Index(
                fields=[
                    "surface",
                    "started_at",
                ]
            ),
            models.Index(
                fields=[
                    "is_active",
                    "last_heartbeat_at",
                ]
            ),
            models.Index(
                fields=[
                    "is_test_session",
                    "started_at",
                ]
            ),
        ]

        constraints = [
            models.CheckConstraint(
                check=Q(
                    duration_ms_snapshot__gt=0,
                ),
                name="audio_playback_duration_gt_zero",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.track.title} · "
            f"{self.session_id}"
        )


class AudioTrackMetric(models.Model):
    """
    Lifetime and current cached metrics for one track.
    """

    id = models.BigAutoField(
        primary_key=True,
    )

    track = models.OneToOneField(
        "audio_catalog.MusicTrack",
        on_delete=models.CASCADE,
        related_name="analytics_metric",
    )

    total_starts = models.PositiveBigIntegerField(
        default=0,
    )

    total_qualified_plays = models.PositiveBigIntegerField(
        default=0,
    )

    total_unique_listeners = models.PositiveBigIntegerField(
        default=0,
    )

    total_listened_ms = models.PositiveBigIntegerField(
        default=0,
    )

    total_completions = models.PositiveBigIntegerField(
        default=0,
    )

    total_early_skips = models.PositiveBigIntegerField(
        default=0,
    )

    total_usages = models.PositiveBigIntegerField(
        default=0,
    )

    active_usages = models.PositiveBigIntegerField(
        default=0,
    )

    total_unique_usage_users = models.PositiveBigIntegerField(
        default=0,
    )

    trending_score = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        default=0,
        db_index=True,
    )

    quality_score = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=0,
    )

    usage_score = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=0,
    )

    last_played_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = "Audio Track Metric"
        verbose_name_plural = "Audio Track Metrics"

        ordering = [
            "-trending_score",
            "-total_qualified_plays",
            "track_id",
        ]

        indexes = [
            models.Index(
                fields=[
                    "trending_score",
                    "total_qualified_plays",
                ]
            ),
            models.Index(
                fields=[
                    "last_played_at",
                ]
            ),
        ]

    def __str__(self) -> str:
        return f"Metrics · {self.track.title}"


class AudioTrackDailyMetric(models.Model):
    """
    Daily aggregate used by trending and reporting.
    """

    id = models.BigAutoField(
        primary_key=True,
    )

    track = models.ForeignKey(
        "audio_catalog.MusicTrack",
        on_delete=models.CASCADE,
        related_name="daily_analytics",
    )

    date = models.DateField(
        db_index=True,
    )

    starts = models.PositiveBigIntegerField(
        default=0,
    )

    qualified_plays = models.PositiveBigIntegerField(
        default=0,
    )

    unique_listeners = models.PositiveBigIntegerField(
        default=0,
    )

    total_listened_ms = models.PositiveBigIntegerField(
        default=0,
    )

    completions = models.PositiveBigIntegerField(
        default=0,
    )

    early_skips = models.PositiveBigIntegerField(
        default=0,
    )

    usages = models.PositiveBigIntegerField(
        default=0,
    )

    unique_usage_users = models.PositiveBigIntegerField(
        default=0,
    )

    trending_score = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        default=0,
        db_index=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = "Audio Track Daily Metric"
        verbose_name_plural = "Audio Track Daily Metrics"

        ordering = [
            "-date",
            "-trending_score",
            "track_id",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "track",
                    "date",
                ],
                name="audio_unique_track_daily_metric",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "date",
                    "trending_score",
                ]
            ),
            models.Index(
                fields=[
                    "track",
                    "date",
                ]
            ),
        ]

    def __str__(self) -> str:
        return f"{self.track.title} · {self.date}"


class AudioTrackDailyListener(models.Model):
    """
    Exact unique-listener guard per track and day.
    """

    id = models.BigAutoField(
        primary_key=True,
    )

    track = models.ForeignKey(
        "audio_catalog.MusicTrack",
        on_delete=models.CASCADE,
        related_name="daily_listener_rows",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="audio_daily_listener_rows",
    )

    date = models.DateField(
        db_index=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "track",
                    "user",
                    "date",
                ],
                name="audio_unique_daily_track_listener",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "date",
                    "track",
                ]
            ),
        ]


class AudioTrackUsageUser(models.Model):
    """
    Lifetime unique user usage guard.

    One row means this user has used this track at least once.
    """

    id = models.BigAutoField(
        primary_key=True,
    )

    track = models.ForeignKey(
        "audio_catalog.MusicTrack",
        on_delete=models.CASCADE,
        related_name="lifetime_usage_users",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="audio_lifetime_usage_rows",
    )

    first_used_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )

    class Meta:
        verbose_name = "Audio Track Usage User"
        verbose_name_plural = "Audio Track Usage Users"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "track",
                    "user",
                ],
                name=(
                    "audio_unique_lifetime_track_usage_user"
                ),
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "track",
                    "first_used_at",
                ]
            ),
            models.Index(
                fields=[
                    "user",
                    "first_used_at",
                ]
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.user_id} · "
            f"{self.track_id}"
        )


class AudioTrackDailyUsageUser(models.Model):
    """
    Daily unique user usage guard.
    """

    id = models.BigAutoField(
        primary_key=True,
    )

    track = models.ForeignKey(
        "audio_catalog.MusicTrack",
        on_delete=models.CASCADE,
        related_name="daily_usage_users",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="audio_daily_usage_rows",
    )

    date = models.DateField(
        db_index=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "Audio Track Daily Usage User"
        verbose_name_plural = (
            "Audio Track Daily Usage Users"
        )

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "track",
                    "user",
                    "date",
                ],
                name=(
                    "audio_unique_daily_track_usage_user"
                ),
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "date",
                    "track",
                ]
            ),
            models.Index(
                fields=[
                    "user",
                    "date",
                ]
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.user_id} · "
            f"{self.track_id} · "
            f"{self.date}"
        )
        
        
class AudioUserTrackAffinity(models.Model):
    """
    Long-term user affinity for one track.
    """

    id = models.BigAutoField(
        primary_key=True,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="audio_track_affinities",
    )

    track = models.ForeignKey(
        "audio_catalog.MusicTrack",
        on_delete=models.CASCADE,
        related_name="user_affinities",
    )

    total_listened_ms = models.PositiveBigIntegerField(
        default=0,
    )

    qualified_play_count = models.PositiveBigIntegerField(
        default=0,
    )

    completion_count = models.PositiveBigIntegerField(
        default=0,
    )

    early_skip_count = models.PositiveBigIntegerField(
        default=0,
    )

    usage_count = models.PositiveBigIntegerField(
        default=0,
    )

    affinity_score = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        default=0,
        db_index=True,
    )

    first_listened_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    last_listened_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )

    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = "Audio User Track Affinity"
        verbose_name_plural = "Audio User Track Affinities"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "user",
                    "track",
                ],
                name="audio_unique_user_track_affinity",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "user",
                    "affinity_score",
                ]
            ),
            models.Index(
                fields=[
                    "track",
                    "affinity_score",
                ]
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.user_id} · "
            f"{self.track.title}"
        )