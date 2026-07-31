# apps/audio_catalog/analytics/services.py

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import (
    NotFound,
    PermissionDenied,
    ValidationError,
)

from apps.audio_catalog.analytics.constants import (
    COMPLETION_PERCENT,
    EARLY_SKIP_MAX_MS,
    HEARTBEAT_TOLERANCE_MS,
    MAX_HEARTBEAT_DELTA_MS,
    QUALIFIED_MIN_LISTEN_MS,
    QUALIFIED_MIN_PERCENT,
)
from apps.audio_catalog.models import (
    AudioPlaybackSession,
    AudioTrackDailyListener,
    AudioTrackDailyMetric,
    AudioTrackDailyUsageUser,
    AudioTrackMetric,
    AudioTrackUsageUser,
    AudioUsageGrant,
    AudioUserTrackAffinity,
    MusicTrack,
    MusicTrackVariant,
    PlaybackEndReason,
)


@dataclass(frozen=True)
class PlaybackResult:
    session: AudioPlaybackSession
    accepted_delta_ms: int = 0
    duplicate: bool = False


def hash_device_id(
    raw_device_id: str,
) -> str:
    """
    Store a non-reversible device identifier.
    """

    value = (
        raw_device_id
        or ""
    ).strip()

    if not value:
        return ""

    return hashlib.sha256(
        value.encode(
            "utf-8",
        )
    ).hexdigest()


def _get_track(
    *,
    track_public_id: UUID,
    user,
) -> MusicTrack:
    try:
        track = (
            MusicTrack.objects
            .select_related(
                "catalog",
            )
            .get(
                public_id=track_public_id,
            )
        )
    except MusicTrack.DoesNotExist as exc:
        raise NotFound(
            "Track not found."
        ) from exc

    if track.is_test_asset:
        if not getattr(
            user,
            "is_staff",
            False,
        ):
            raise PermissionDenied(
                "This track is not available."
            )

        return track

    if (
        track.status
        != MusicTrack.Status.PUBLISHED
        or not track.allow_streaming
        or not track.catalog.is_active
    ):
        raise PermissionDenied(
            "This track is not available."
        )

    return track


def _get_variant(
    *,
    track: MusicTrack,
    variant_public_id: UUID | None,
) -> MusicTrackVariant:
    queryset = MusicTrackVariant.objects.filter(
        track=track,
        is_active=True,
        is_converted=True,
        is_streamable=True,
    )

    if variant_public_id:
        try:
            return queryset.get(
                public_id=variant_public_id,
            )
        except MusicTrackVariant.DoesNotExist as exc:
            raise NotFound(
                "Playback variant not found."
            ) from exc

    variant = (
        queryset
        .order_by(
            "-is_default",
            "sort_order",
            "id",
        )
        .first()
    )

    if variant is None:
        raise PermissionDenied(
            "No playable variant is available."
        )

    return variant


def _get_or_create_metric(
    track: MusicTrack,
) -> AudioTrackMetric:
    metric, _ = (
        AudioTrackMetric.objects
        .get_or_create(
            track=track,
        )
    )

    return metric


def _get_or_create_daily_metric(
    *,
    track: MusicTrack,
    metric_date: date,
) -> AudioTrackDailyMetric:
    metric, _ = (
        AudioTrackDailyMetric.objects
        .get_or_create(
            track=track,
            date=metric_date,
        )
    )

    return metric


def start_playback(
    *,
    user,
    session_id: UUID,
    track_public_id: UUID,
    variant_public_id: UUID | None,
    surface: str,
    source_context: dict[str, Any],
    client_platform: str,
    client_version: str,
    raw_device_id: str,
) -> PlaybackResult:
    """
    Start one idempotent playback session.
    """

    existing = (
        AudioPlaybackSession.objects
        .select_related(
            "track",
            "variant",
        )
        .filter(
            session_id=session_id,
        )
        .first()
    )

    if existing is not None:
        if (
            existing.user_id
            != getattr(
                user,
                "pk",
                None,
            )
        ):
            raise PermissionDenied(
                "Playback session ownership mismatch."
            )

        return PlaybackResult(
            session=existing,
            duplicate=True,
        )

    track = _get_track(
        track_public_id=track_public_id,
        user=user,
    )

    variant = _get_variant(
        track=track,
        variant_public_id=variant_public_id,
    )

    duration_ms = max(
        1,
        int(
            variant.duration_ms
            or track.duration_ms
            or 1
        ),
    )

    now = timezone.now()

    try:
        with transaction.atomic():
            session = (
                AudioPlaybackSession.objects
                .create(
                    session_id=session_id,
                    user=user,
                    track=track,
                    variant=variant,
                    surface=surface,
                    source_context=source_context,
                    client_platform=(
                        client_platform
                        or ""
                    )[:24],
                    client_version=(
                        client_version
                        or ""
                    )[:40],
                    device_id_hash=hash_device_id(
                        raw_device_id
                    ),
                    duration_ms_snapshot=duration_ms,
                    play_counted=True,
                    is_test_session=track.is_test_asset,
                    started_at=now,
                    last_heartbeat_at=now,
                )
            )

            if not track.is_test_asset:
                _get_or_create_metric(
                    track
                )

                _get_or_create_daily_metric(
                    track=track,
                    metric_date=now.date(),
                )

                AudioTrackMetric.objects.filter(
                    track=track,
                ).update(
                    total_starts=F(
                        "total_starts"
                    )
                    + 1,
                    last_played_at=now,
                )

                AudioTrackDailyMetric.objects.filter(
                    track=track,
                    date=now.date(),
                ).update(
                    starts=F(
                        "starts"
                    )
                    + 1,
                )

    except IntegrityError:
        session = (
            AudioPlaybackSession.objects
            .select_related(
                "track",
                "variant",
            )
            .get(
                session_id=session_id,
            )
        )

        return PlaybackResult(
            session=session,
            duplicate=True,
        )

    return PlaybackResult(
        session=session,
    )


def _qualified_threshold_ms(
    session: AudioPlaybackSession,
) -> int:
    percentage_threshold = int(
        session.duration_ms_snapshot
        * QUALIFIED_MIN_PERCENT
    )

    return max(
        1,
        min(
            QUALIFIED_MIN_LISTEN_MS,
            percentage_threshold,
        ),
    )


def _completion_threshold_ms(
    session: AudioPlaybackSession,
) -> int:
    return max(
        1,
        int(
            session.duration_ms_snapshot
            * COMPLETION_PERCENT
        ),
    )


def _accepted_listen_delta(
    *,
    session: AudioPlaybackSession,
    requested_delta_ms: int,
    now,
) -> int:
    if requested_delta_ms <= 0:
        return 0

    previous_at = (
        session.last_heartbeat_at
        or session.started_at
        or now
    )

    elapsed_ms = max(
        0,
        int(
            (
                now
                - previous_at
            ).total_seconds()
            * 1000
        ),
    )

    plausible_ms = (
        elapsed_ms
        + HEARTBEAT_TOLERANCE_MS
    )

    return max(
        0,
        min(
            requested_delta_ms,
            plausible_ms,
            MAX_HEARTBEAT_DELTA_MS,
        ),
    )


def _increment_unique_listener(
    *,
    session: AudioPlaybackSession,
    now,
) -> None:
    if (
        session.is_test_session
        or session.user_id is None
    ):
        return

    try:
        _, created = (
            AudioTrackDailyListener.objects
            .get_or_create(
                track=session.track,
                user_id=session.user_id,
                date=now.date(),
            )
        )
    except IntegrityError:
        created = False

    if created:
        AudioTrackDailyMetric.objects.filter(
            track=session.track,
            date=now.date(),
        ).update(
            unique_listeners=F(
                "unique_listeners"
            )
            + 1,
        )

    affinity, affinity_created = (
        AudioUserTrackAffinity.objects
        .get_or_create(
            user_id=session.user_id,
            track=session.track,
            defaults={
                "first_listened_at": now,
            },
        )
    )

    if affinity_created:
        AudioTrackMetric.objects.filter(
            track=session.track,
        ).update(
            total_unique_listeners=F(
                "total_unique_listeners"
            )
            + 1,
        )


def _update_affinity(
    *,
    session: AudioPlaybackSession,
    listened_delta_ms: int = 0,
    qualified_increment: int = 0,
    completion_increment: int = 0,
    early_skip_increment: int = 0,
    now,
) -> None:
    if (
        session.is_test_session
        or session.user_id is None
    ):
        return

    affinity, _ = (
        AudioUserTrackAffinity.objects
        .get_or_create(
            user_id=session.user_id,
            track=session.track,
            defaults={
                "first_listened_at": now,
            },
        )
    )

    AudioUserTrackAffinity.objects.filter(
        pk=affinity.pk,
    ).update(
        total_listened_ms=F(
            "total_listened_ms"
        )
        + listened_delta_ms,
        qualified_play_count=F(
            "qualified_play_count"
        )
        + qualified_increment,
        completion_count=F(
            "completion_count"
        )
        + completion_increment,
        early_skip_count=F(
            "early_skip_count"
        )
        + early_skip_increment,
        affinity_score=(
            F(
                "affinity_score"
            )
            + qualified_increment
            * 1
            + completion_increment
            * 2
            - early_skip_increment
            * 1
            + listened_delta_ms
            / 60_000
            * 0.05
        ),
        last_listened_at=now,
    )


def heartbeat_playback(
    *,
    user,
    session_id: UUID,
    sequence: int,
    position_ms: int,
    listened_delta_ms: int,
    is_playing: bool,
    is_foreground: bool,
) -> PlaybackResult:
    """
    Apply one idempotent heartbeat.
    """

    now = timezone.now()

    with transaction.atomic():
        try:
            session = (
                AudioPlaybackSession.objects
                .select_for_update()
                .select_related(
                    "track",
                    "variant",
                )
                .get(
                    session_id=session_id,
                )
            )
        except AudioPlaybackSession.DoesNotExist as exc:
            raise NotFound(
                "Playback session not found."
            ) from exc

        if (
            session.user_id
            != getattr(
                user,
                "pk",
                None,
            )
        ):
            raise PermissionDenied(
                "Playback session ownership mismatch."
            )

        if sequence <= session.last_sequence:
            return PlaybackResult(
                session=session,
                duplicate=True,
            )

        accepted_delta_ms = 0

        if (
            session.is_active
            and is_playing
            and is_foreground
        ):
            accepted_delta_ms = (
                _accepted_listen_delta(
                    session=session,
                    requested_delta_ms=(
                        listened_delta_ms
                    ),
                    now=now,
                )
            )

        previous_qualified = (
            session.qualified_play
        )
        previous_completed = (
            session.completed
        )

        session.last_sequence = sequence
        session.max_position_ms = max(
            session.max_position_ms,
            min(
                max(
                    0,
                    position_ms,
                ),
                session.duration_ms_snapshot,
            ),
        )

        session.listened_ms += (
            accepted_delta_ms
        )

        qualified_now = (
            session.listened_ms
            >= _qualified_threshold_ms(
                session
            )
        )

        completed_now = (
            session.max_position_ms
            >= _completion_threshold_ms(
                session
            )
            or session.listened_ms
            >= _completion_threshold_ms(
                session
            )
        )

        if qualified_now:
            session.qualified_play = True

        if completed_now:
            session.completed = True

        session.last_heartbeat_at = now

        session.save(
            update_fields=[
                "last_sequence",
                "max_position_ms",
                "listened_ms",
                "qualified_play",
                "completed",
                "last_heartbeat_at",
                "updated_at",
            ]
        )

        if not session.is_test_session:
            _get_or_create_metric(
                session.track
            )

            _get_or_create_daily_metric(
                track=session.track,
                metric_date=now.date(),
            )

            metric_updates = {
                "total_listened_ms": (
                    F(
                        "total_listened_ms"
                    )
                    + accepted_delta_ms
                ),
                "last_played_at": now,
            }

            daily_updates = {
                "total_listened_ms": (
                    F(
                        "total_listened_ms"
                    )
                    + accepted_delta_ms
                ),
            }

            qualified_increment = 0
            completion_increment = 0

            if (
                session.qualified_play
                and not previous_qualified
            ):
                qualified_increment = 1

                metric_updates[
                    "total_qualified_plays"
                ] = (
                    F(
                        "total_qualified_plays"
                    )
                    + 1
                )

                daily_updates[
                    "qualified_plays"
                ] = (
                    F(
                        "qualified_plays"
                    )
                    + 1
                )

                _increment_unique_listener(
                    session=session,
                    now=now,
                )

            if (
                session.completed
                and not previous_completed
            ):
                completion_increment = 1

                metric_updates[
                    "total_completions"
                ] = (
                    F(
                        "total_completions"
                    )
                    + 1
                )

                daily_updates[
                    "completions"
                ] = (
                    F(
                        "completions"
                    )
                    + 1
                )

            AudioTrackMetric.objects.filter(
                track=session.track,
            ).update(
                **metric_updates
            )

            AudioTrackDailyMetric.objects.filter(
                track=session.track,
                date=now.date(),
            ).update(
                **daily_updates
            )

            _update_affinity(
                session=session,
                listened_delta_ms=(
                    accepted_delta_ms
                ),
                qualified_increment=(
                    qualified_increment
                ),
                completion_increment=(
                    completion_increment
                ),
                now=now,
            )

    return PlaybackResult(
        session=session,
        accepted_delta_ms=accepted_delta_ms,
    )


def end_playback(
    *,
    user,
    session_id: UUID,
    sequence: int,
    position_ms: int,
    reason: str,
) -> PlaybackResult:
    """
    End one playback session idempotently.
    """

    now = timezone.now()

    with transaction.atomic():
        try:
            session = (
                AudioPlaybackSession.objects
                .select_for_update()
                .select_related(
                    "track",
                )
                .get(
                    session_id=session_id,
                )
            )
        except AudioPlaybackSession.DoesNotExist as exc:
            raise NotFound(
                "Playback session not found."
            ) from exc

        if (
            session.user_id
            != getattr(
                user,
                "pk",
                None,
            )
        ):
            raise PermissionDenied(
                "Playback session ownership mismatch."
            )

        if not session.is_active:
            return PlaybackResult(
                session=session,
                duplicate=True,
            )

        if sequence < session.last_sequence:
            raise ValidationError(
                {
                    "sequence": (
                        "Sequence is older than "
                        "the latest heartbeat."
                    )
                }
            )

        previous_early_skip = (
            session.early_skipped
        )

        session.last_sequence = max(
            sequence,
            session.last_sequence,
        )

        session.max_position_ms = max(
            session.max_position_ms,
            min(
                max(
                    0,
                    position_ms,
                ),
                session.duration_ms_snapshot,
            ),
        )

        session.is_active = False
        session.end_reason = reason
        session.ended_at = now
        session.last_heartbeat_at = now

        if (
            reason
            == PlaybackEndReason.COMPLETED
        ):
            session.completed = True

        if (
            not session.qualified_play
            and session.listened_ms
            <= EARLY_SKIP_MAX_MS
            and reason
            in {
                PlaybackEndReason.SWITCHED_TRACK,
                PlaybackEndReason.DISMISSED,
                PlaybackEndReason.PAUSED,
            }
        ):
            session.early_skipped = True

        if (
            reason
            == PlaybackEndReason.USED_IN_CONTENT
        ):
            session.used_in_content = True

        session.save(
            update_fields=[
                "last_sequence",
                "max_position_ms",
                "is_active",
                "end_reason",
                "ended_at",
                "last_heartbeat_at",
                "completed",
                "early_skipped",
                "used_in_content",
                "updated_at",
            ]
        )

        if (
            not session.is_test_session
            and session.early_skipped
            and not previous_early_skip
        ):
            _get_or_create_metric(
                session.track
            )

            _get_or_create_daily_metric(
                track=session.track,
                metric_date=now.date(),
            )

            AudioTrackMetric.objects.filter(
                track=session.track,
            ).update(
                total_early_skips=F(
                    "total_early_skips"
                )
                + 1,
            )

            AudioTrackDailyMetric.objects.filter(
                track=session.track,
                date=now.date(),
            ).update(
                early_skips=F(
                    "early_skips"
                )
                + 1,
            )

            _update_affinity(
                session=session,
                early_skip_increment=1,
                now=now,
            )

    return PlaybackResult(
        session=session,
    )

def _resolve_usage_user_id(
    grant: AudioUsageGrant,
    actor_id: int | None = None,
) -> int | None:
    """
    Resolve the user responsible for the usage.

    granted_to is authoritative. actor_id is a fallback.
    """

    return (
        grant.granted_to_id
        or actor_id
    )


def record_usage_grant_activated(
    *,
    grant_id: int,
    actor_id: int | None = None,
) -> bool:
    """
    Count one activated AudioUsageGrant exactly once.

    Returns True when new analytics were recorded.
    """

    now = timezone.now()

    with transaction.atomic():
        try:
            grant = (
                AudioUsageGrant.objects
                .select_for_update()
                .select_related(
                    "track",
                    "granted_to",
                )
                .get(
                    pk=grant_id,
                )
            )
        except AudioUsageGrant.DoesNotExist:
            return False

        if (
            grant.status
            != AudioUsageGrant.Status.ACTIVE
        ):
            return False

        if grant.analytics_activated_at:
            return False

        track = grant.track

        # Test assets never affect production analytics.
        if track.is_test_asset:
            AudioUsageGrant.objects.filter(
                pk=grant.pk,
                analytics_activated_at__isnull=True,
            ).update(
                analytics_activated_at=now,
            )

            return True

        metric_date = timezone.localdate(
            grant.created_at
            or now
        )

        _get_or_create_metric(
            track
        )

        _get_or_create_daily_metric(
            track=track,
            metric_date=metric_date,
        )

        AudioTrackMetric.objects.filter(
            track=track,
        ).update(
            total_usages=F(
                "total_usages"
            )
            + 1,
            active_usages=F(
                "active_usages"
            )
            + 1,
            last_used_at=now,
        )

        AudioTrackDailyMetric.objects.filter(
            track=track,
            date=metric_date,
        ).update(
            usages=F(
                "usages"
            )
            + 1,
        )

        user_id = _resolve_usage_user_id(
            grant,
            actor_id=actor_id,
        )

        if user_id is not None:
            try:
                _, lifetime_created = (
                    AudioTrackUsageUser.objects
                    .get_or_create(
                        track=track,
                        user_id=user_id,
                        defaults={
                            "first_used_at": now,
                        },
                    )
                )
            except IntegrityError:
                lifetime_created = False

            try:
                _, daily_created = (
                    AudioTrackDailyUsageUser.objects
                    .get_or_create(
                        track=track,
                        user_id=user_id,
                        date=metric_date,
                    )
                )
            except IntegrityError:
                daily_created = False

            if lifetime_created:
                AudioTrackMetric.objects.filter(
                    track=track,
                ).update(
                    total_unique_usage_users=F(
                        "total_unique_usage_users"
                    )
                    + 1,
                )

            if daily_created:
                AudioTrackDailyMetric.objects.filter(
                    track=track,
                    date=metric_date,
                ).update(
                    unique_usage_users=F(
                        "unique_usage_users"
                    )
                    + 1,
                )

            affinity, _ = (
                AudioUserTrackAffinity.objects
                .get_or_create(
                    user_id=user_id,
                    track=track,
                    defaults={
                        "first_listened_at": now,
                    },
                )
            )

            AudioUserTrackAffinity.objects.filter(
                pk=affinity.pk,
            ).update(
                usage_count=F(
                    "usage_count"
                )
                + 1,
                affinity_score=F(
                    "affinity_score"
                )
                + 5,
                last_used_at=now,
            )

        updated = (
            AudioUsageGrant.objects
            .filter(
                pk=grant.pk,
                analytics_activated_at__isnull=True,
            )
            .update(
                analytics_activated_at=now,
            )
        )

        return bool(updated)


def record_usage_grant_revoked(
    *,
    grant_id: int,
) -> bool:
    """
    Decrease active usage exactly once.

    Historical total_usages is intentionally preserved.
    """

    now = timezone.now()

    with transaction.atomic():
        try:
            grant = (
                AudioUsageGrant.objects
                .select_for_update()
                .select_related(
                    "track",
                )
                .get(
                    pk=grant_id,
                )
            )
        except AudioUsageGrant.DoesNotExist:
            return False

        if grant.status == AudioUsageGrant.Status.ACTIVE:
            return False

        if grant.analytics_revoked_at:
            return False

        # Activation was never counted, so nothing must be decremented.
        if not grant.analytics_activated_at:
            AudioUsageGrant.objects.filter(
                pk=grant.pk,
                analytics_revoked_at__isnull=True,
            ).update(
                analytics_revoked_at=now,
            )

            return True

        track = grant.track

        if not track.is_test_asset:
            metric = (
                AudioTrackMetric.objects
                .select_for_update()
                .filter(
                    track=track,
                )
                .first()
            )

            if (
                metric is not None
                and metric.active_usages > 0
            ):
                AudioTrackMetric.objects.filter(
                    pk=metric.pk,
                ).update(
                    active_usages=F(
                        "active_usages"
                    )
                    - 1,
                )

        updated = (
            AudioUsageGrant.objects
            .filter(
                pk=grant.pk,
                analytics_revoked_at__isnull=True,
            )
            .update(
                analytics_revoked_at=now,
            )
        )

        return bool(updated)