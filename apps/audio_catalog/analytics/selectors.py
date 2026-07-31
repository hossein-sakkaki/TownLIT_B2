# apps/audio_catalog/analytics/selectors.py

from __future__ import annotations

from django.db.models import (
    Case,
    DecimalField,
    F,
    Value,
    When,
)

from apps.audio_catalog.models import (
    AudioUserTrackAffinity,
)
from apps.audio_catalog.querysets import (
    published_tracks,
)


def trending_tracks():
    """
    Return published tracks ordered by cached trending score.
    """

    return (
        published_tracks()
        .select_related(
            "analytics_metric",
        )
        .annotate(
            resolved_trending_score=Case(
                When(
                    analytics_metric__isnull=False,
                    then=F(
                        "analytics_metric__trending_score"
                    ),
                ),
                default=Value(
                    0,
                ),
                output_field=DecimalField(
                    max_digits=20,
                    decimal_places=6,
                ),
            )
        )
        .order_by(
            "-resolved_trending_score",
            "-published_at",
            "-id",
        )
    )


def recommended_tracks_for_user(
    user,
):
    """
    Initial recommendation selector.

    Prioritizes the user's existing affinity, then global trend.
    """

    preferred_track_ids = list(
        AudioUserTrackAffinity.objects
        .filter(
            user=user,
            affinity_score__gt=0,
        )
        .order_by(
            "-affinity_score",
        )
        .values_list(
            "track_id",
            flat=True,
        )[:100]
    )

    queryset = (
        published_tracks()
        .select_related(
            "analytics_metric",
        )
        .annotate(
            user_preference=Case(
                *[
                    When(
                        pk=track_id,
                        then=Value(
                            max(
                                1,
                                100 - index,
                            )
                        ),
                    )
                    for index, track_id
                    in enumerate(
                        preferred_track_ids
                    )
                ],
                default=Value(
                    0,
                ),
            ),
            resolved_trending_score=Case(
                When(
                    analytics_metric__isnull=False,
                    then=F(
                        "analytics_metric__trending_score"
                    ),
                ),
                default=Value(
                    0,
                ),
                output_field=DecimalField(
                    max_digits=20,
                    decimal_places=6,
                ),
            ),
        )
        .order_by(
            "-user_preference",
            "-resolved_trending_score",
            "-published_at",
        )
    )

    return queryset