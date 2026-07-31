# apps/audio_catalog/analytics/tasks.py

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from apps.audio_catalog.analytics.constants import (
    RAW_SESSION_RETENTION_DAYS,
    STALE_SESSION_MINUTES,
    TRENDING_WINDOW_DAYS,
)
from apps.audio_catalog.analytics.ranking import (
    calculate_daily_trending_score,
    decay_weight,
)
from apps.audio_catalog.analytics.services import (
    record_usage_grant_activated,
    record_usage_grant_revoked,
)
from apps.audio_catalog.models import (
    AudioPlaybackSession,
    AudioTrackDailyListener,
    AudioTrackDailyMetric,
    AudioTrackDailyUsageUser,
    AudioTrackMetric,
    MusicTrack,
    PlaybackEndReason,
)


@shared_task(
    ignore_result=True,
)
def rebuild_audio_trending_scores():
    """
    Recalculate daily and cached track trend scores.
    """

    today = timezone.localdate()

    start_date = (
        today
        - timedelta(
            days=max(
                1,
                TRENDING_WINDOW_DAYS,
            )
            - 1
        )
    )

    track_scores: dict[int, Decimal] = {}

    daily_metrics = (
        AudioTrackDailyMetric.objects
        .filter(
            date__gte=start_date,
            track__is_test_asset=False,
        )
        .select_related(
            "track",
        )
        .iterator()
    )

    for metric in daily_metrics:
        raw_score = (
            calculate_daily_trending_score(
                qualified_plays=(
                    metric.qualified_plays
                ),
                completions=(
                    metric.completions
                ),
                unique_listeners=(
                    metric.unique_listeners
                ),
                total_listened_ms=(
                    metric.total_listened_ms
                ),
                usages=metric.usages,
                unique_usage_users=(
                    metric.unique_usage_users
                ),
                early_skips=(
                    metric.early_skips
                ),
            )
        )

        AudioTrackDailyMetric.objects.filter(
            pk=metric.pk,
        ).update(
            trending_score=raw_score,
        )

        weighted_score = (
            raw_score
            * Decimal(
                str(
                    decay_weight(
                        metric.date,
                        reference_date=today,
                    )
                )
            )
        )

        track_scores[
            metric.track_id
        ] = (
            track_scores.get(
                metric.track_id,
                Decimal("0"),
            )
            + weighted_score
        )

    with transaction.atomic():
        AudioTrackMetric.objects.filter(
            track__is_test_asset=False,
        ).update(
            trending_score=0,
        )

        MusicTrack.objects.filter(
            is_test_asset=False,
        ).update(
            popularity_score=0,
        )

        for track_id, score in (
            track_scores.items()
        ):
            metric, _ = (
                AudioTrackMetric.objects
                .get_or_create(
                    track_id=track_id,
                )
            )

            AudioTrackMetric.objects.filter(
                pk=metric.pk,
            ).update(
                trending_score=score,
            )

            MusicTrack.objects.filter(
                pk=track_id,
            ).update(
                popularity_score=max(
                    0,
                    int(score),
                )
            )


@shared_task(
    ignore_result=True,
)
def close_stale_audio_playback_sessions():
    """
    Close sessions that stopped sending heartbeats.
    """

    now = timezone.now()

    cutoff = (
        now
        - timedelta(
            minutes=STALE_SESSION_MINUTES,
        )
    )

    AudioPlaybackSession.objects.filter(
        is_active=True,
        last_heartbeat_at__lt=cutoff,
    ).update(
        is_active=False,
        end_reason=PlaybackEndReason.STALE,
        ended_at=now,
        updated_at=now,
    )


@shared_task(
    ignore_result=True,
)
def purge_old_audio_playback_sessions():
    """
    Delete old raw sessions while keeping aggregates.
    """

    cutoff = (
        timezone.now()
        - timedelta(
            days=RAW_SESSION_RETENTION_DAYS,
        )
    )

    AudioPlaybackSession.objects.filter(
        started_at__lt=cutoff,
        is_active=False,
    ).delete()


@shared_task(
    ignore_result=True,
)
def purge_old_audio_unique_listener_rows():
    """
    Delete expired daily uniqueness guards.
    """

    cutoff = (
        timezone.localdate()
        - timedelta(
            days=RAW_SESSION_RETENTION_DAYS,
        )
    )

    AudioTrackDailyListener.objects.filter(
        date__lt=cutoff,
    ).delete()

    AudioTrackDailyUsageUser.objects.filter(
        date__lt=cutoff,
    ).delete()


@shared_task(
    ignore_result=True,
    autoretry_for=(
        Exception,
    ),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
)
def process_audio_usage_grant_activated(
    grant_id: int,
    actor_id: int | None = None,
):
    """
    Count one activated usage grant.
    """

    record_usage_grant_activated(
        grant_id=grant_id,
        actor_id=actor_id,
    )


@shared_task(
    ignore_result=True,
    autoretry_for=(
        Exception,
    ),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
)
def process_audio_usage_grant_revoked(
    grant_id: int,
):
    """
    Decrease active usage for one revoked grant.
    """

    record_usage_grant_revoked(
        grant_id=grant_id,
    )