# apps/audio_catalog/analytics/ranking.py

from __future__ import annotations

import math
from datetime import date
from decimal import Decimal

from apps.audio_catalog.analytics.constants import (
    TRENDING_HALF_LIFE_DAYS,
    TRENDING_WEIGHTS,
)


def decay_weight(
    metric_date: date,
    *,
    reference_date: date,
) -> float:
    """
    Apply exponential time decay.
    """

    age_days = max(
        0,
        (
            reference_date
            - metric_date
        ).days,
    )

    half_life = max(
        0.1,
        TRENDING_HALF_LIFE_DAYS,
    )

    return math.pow(
        0.5,
        age_days / half_life,
    )


def calculate_daily_trending_score(
    *,
    qualified_plays: int,
    completions: int,
    unique_listeners: int,
    total_listened_ms: int,
    usages: int,
    unique_usage_users: int,
    early_skips: int,
) -> Decimal:
    """
    Calculate one non-decayed daily score.
    """

    listened_minutes = (
        max(
            0,
            total_listened_ms,
        )
        / 60_000
    )

    score = (
        qualified_plays
        * float(
            TRENDING_WEIGHTS[
                "qualified_play"
            ]
        )
        + completions
        * float(
            TRENDING_WEIGHTS[
                "completion"
            ]
        )
        + unique_listeners
        * float(
            TRENDING_WEIGHTS[
                "unique_listener"
            ]
        )
        + usages
        * float(
            TRENDING_WEIGHTS[
                "usage"
            ]
        )
        + unique_usage_users
        * float(
            TRENDING_WEIGHTS[
                "unique_usage_user"
            ]
        )
        + listened_minutes
        * float(
            TRENDING_WEIGHTS[
                "listened_minute"
            ]
        )
        - early_skips
        * float(
            TRENDING_WEIGHTS[
                "early_skip_penalty"
            ]
        )
    )

    return Decimal(
        str(
            max(
                0.0,
                score,
            )
        )
    )