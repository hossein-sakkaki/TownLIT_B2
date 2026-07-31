# apps/audio_catalog/analytics/constants.py

from __future__ import annotations

from django.conf import settings


def _setting(
    name: str,
    default,
):
    """
    Read one optional audio analytics setting.
    """

    config = getattr(
        settings,
        "AUDIO_ANALYTICS",
        {},
    )

    return config.get(
        name,
        default,
    )


HEARTBEAT_INTERVAL_SECONDS = int(
    _setting(
        "heartbeat_interval_seconds",
        15,
    )
)

HEARTBEAT_TOLERANCE_MS = int(
    _setting(
        "heartbeat_tolerance_ms",
        5_000,
    )
)

MAX_HEARTBEAT_DELTA_MS = int(
    _setting(
        "max_heartbeat_delta_ms",
        30_000,
    )
)

QUALIFIED_MIN_LISTEN_MS = int(
    _setting(
        "qualified_min_listen_ms",
        10_000,
    )
)

QUALIFIED_MIN_PERCENT = float(
    _setting(
        "qualified_min_percent",
        0.25,
    )
)

COMPLETION_PERCENT = float(
    _setting(
        "completion_percent",
        0.90,
    )
)

EARLY_SKIP_MAX_MS = int(
    _setting(
        "early_skip_max_ms",
        5_000,
    )
)

STALE_SESSION_MINUTES = int(
    _setting(
        "stale_session_minutes",
        30,
    )
)

RAW_SESSION_RETENTION_DAYS = int(
    _setting(
        "raw_session_retention_days",
        90,
    )
)

TRENDING_WINDOW_DAYS = int(
    _setting(
        "trending_window_days",
        7,
    )
)

TRENDING_HALF_LIFE_DAYS = float(
    _setting(
        "trending_half_life_days",
        3.0,
    )
)

TRENDING_WEIGHTS = _setting(
    "trending_weights",
    {
        "qualified_play": 1.0,
        "completion": 2.0,
        "unique_listener": 2.0,
        "usage": 6.0,
        "unique_usage_user": 8.0,
        "early_skip_penalty": 2.0,
        "listened_minute": 0.08,
    },
)