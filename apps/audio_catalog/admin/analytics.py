# apps/audio_catalog/admin/analytics.py

from __future__ import annotations

from django.contrib import admin, messages
from django.utils.html import format_html

from apps.audio_catalog.analytics.tasks import (
    rebuild_audio_trending_scores,
)
from apps.audio_catalog.models import (
    AudioPlaybackSession,
    AudioTrackDailyMetric,
    AudioTrackMetric,
    AudioUserTrackAffinity,
)

from .shared import (
    LargeResultAdminMixin,
    linked_object,
    status_badge,
)


@admin.action(
    description="Rebuild audio trending scores",
)
def rebuild_trending_scores(
    modeladmin,
    request,
    queryset,
):
    rebuild_audio_trending_scores.delay()

    modeladmin.message_user(
        request,
        "Trending-score rebuild was queued.",
        level=messages.SUCCESS,
    )


@admin.register(AudioTrackMetric)
class AudioTrackMetricAdmin(
    LargeResultAdminMixin,
    admin.ModelAdmin,
):
    list_display = (
        "track_link",
        "total_starts",
        "total_qualified_plays",
        "total_unique_listeners",
        "completion_rate",
        "skip_rate",
        "total_usages",
        "active_usages",
        "trending_score",
        "last_played_at",
        "last_used_at",
    )

    list_filter = (
        "track__catalog",
        "track__categories",
        "track__genres",
        "track__moods",
        "last_played_at",
        "last_used_at",
    )

    search_fields = (
        "track__title",
        "track__slug",
        "track__public_id",
    )

    readonly_fields = (
        "track",
        "total_starts",
        "total_qualified_plays",
        "total_unique_listeners",
        "total_listened_ms",
        "total_completions",
        "total_early_skips",
        "total_usages",
        "active_usages",
        "total_unique_usage_users",
        "trending_score",
        "quality_score",
        "usage_score",
        "last_played_at",
        "last_used_at",
        "updated_at",
    )

    actions = (
        rebuild_trending_scores,
    )

    list_select_related = (
        "track",
        "track__catalog",
    )

    ordering = (
        "-trending_score",
        "-total_qualified_plays",
    )

    def has_add_permission(
        self,
        request,
    ):
        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return False

    @admin.display(
        description="Track",
        ordering="track__title",
    )
    def track_link(self, obj):
        return linked_object(
            obj.track,
        )

    @admin.display(
        description="Completion rate",
    )
    def completion_rate(self, obj):
        if not obj.total_qualified_plays:
            return "0.0%"

        value = (
            obj.total_completions
            / obj.total_qualified_plays
            * 100
        )

        return f"{value:.1f}%"

    @admin.display(
        description="Skip rate",
    )
    def skip_rate(self, obj):
        if not obj.total_starts:
            return "0.0%"

        value = (
            obj.total_early_skips
            / obj.total_starts
            * 100
        )

        return f"{value:.1f}%"


@admin.register(AudioTrackDailyMetric)
class AudioTrackDailyMetricAdmin(
    LargeResultAdminMixin,
    admin.ModelAdmin,
):
    list_display = (
        "date",
        "track_link",
        "starts",
        "qualified_plays",
        "unique_listeners",
        "completions",
        "early_skips",
        "usages",
        "unique_usage_users",
        "total_listened_ms",
        "trending_score",
    )

    list_filter = (
        "date",
        "track__catalog",
        "track__categories",
        "track__genres",
        "track__moods",
    )

    search_fields = (
        "track__title",
        "track__slug",
    )

    readonly_fields = (
        "track",
        "date",
        "starts",
        "qualified_plays",
        "unique_listeners",
        "total_listened_ms",
        "completions",
        "early_skips",
        "usages",
        "unique_usage_users",
        "trending_score",
        "created_at",
        "updated_at",
    )

    list_select_related = (
        "track",
        "track__catalog",
    )

    ordering = (
        "-date",
        "-trending_score",
    )

    def has_add_permission(
        self,
        request,
    ):
        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return False

    @admin.display(
        description="Track",
        ordering="track__title",
    )
    def track_link(self, obj):
        return linked_object(
            obj.track,
        )


@admin.register(AudioPlaybackSession)
class AudioPlaybackSessionAdmin(
    LargeResultAdminMixin,
    admin.ModelAdmin,
):
    list_display = (
        "session_id",
        "track_link",
        "user",
        "surface",
        "listened_ms",
        "max_position_ms",
        "session_state",
        "qualified_play",
        "completed",
        "early_skipped",
        "started_at",
        "ended_at",
    )

    list_filter = (
        "surface",
        "qualified_play",
        "completed",
        "early_skipped",
        "used_in_content",
        "is_test_session",
        "is_active",
        "end_reason",
        "started_at",
    )

    search_fields = (
        "session_id",
        "track__title",
        "track__slug",
        "user__email",
        "device_id_hash",
    )

    readonly_fields = (
        "public_id",
        "session_id",
        "user",
        "track",
        "variant",
        "surface",
        "source_context",
        "client_platform",
        "client_version",
        "device_id_hash",
        "duration_ms_snapshot",
        "max_position_ms",
        "listened_ms",
        "last_sequence",
        "play_counted",
        "qualified_play",
        "completed",
        "early_skipped",
        "used_in_content",
        "is_test_session",
        "is_active",
        "end_reason",
        "started_at",
        "last_heartbeat_at",
        "ended_at",
        "created_at",
        "updated_at",
    )

    list_select_related = (
        "track",
        "variant",
        "user",
    )

    ordering = (
        "-started_at",
        "-id",
    )

    def has_add_permission(
        self,
        request,
    ):
        return False

    def has_change_permission(
        self,
        request,
        obj=None,
    ):
        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return False

    @admin.display(
        description="Track",
        ordering="track__title",
    )
    def track_link(self, obj):
        return linked_object(
            obj.track,
        )

    @admin.display(
        description="State",
    )
    def session_state(self, obj):
        if obj.is_active:
            return status_badge(
                "Active",
                background="#0b76b7",
            )

        return status_badge(
            obj.end_reason or "Ended",
            background="#666666",
        )


@admin.register(AudioUserTrackAffinity)
class AudioUserTrackAffinityAdmin(
    LargeResultAdminMixin,
    admin.ModelAdmin,
):
    list_display = (
        "user",
        "track_link",
        "total_listened_ms",
        "qualified_play_count",
        "completion_count",
        "early_skip_count",
        "usage_count",
        "affinity_score",
        "last_listened_at",
        "last_used_at",
    )

    list_filter = (
        "track__catalog",
        "last_listened_at",
        "last_used_at",
    )

    search_fields = (
        "user__email",
        "track__title",
        "track__slug",
    )

    readonly_fields = (
        "user",
        "track",
        "total_listened_ms",
        "qualified_play_count",
        "completion_count",
        "early_skip_count",
        "usage_count",
        "affinity_score",
        "first_listened_at",
        "last_listened_at",
        "last_used_at",
        "created_at",
        "updated_at",
    )

    list_select_related = (
        "user",
        "track",
    )

    def has_add_permission(
        self,
        request,
    ):
        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return False

    @admin.display(
        description="Track",
        ordering="track__title",
    )
    def track_link(self, obj):
        return linked_object(
            obj.track,
        )