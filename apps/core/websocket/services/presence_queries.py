
# apps/core/websocket/services/presence_queries.py
# =========================================================
#                 Presence Query Services
# =========================================================

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from django.utils import timezone
from django.utils.timesince import timesince

from apps.core.websocket.services.redis_online_manager import (
    get_online_status_for_users,
    get_last_seen,
)


async def get_presence_snapshot(user_ids: Iterable[int]) -> dict[int, bool]:
    """
    Return online/offline status for a list of user IDs.
    """
    normalized = []
    seen = set()

    for raw in user_ids:
        try:
            user_id = int(raw)
        except (TypeError, ValueError):
            continue

        if user_id <= 0 or user_id in seen:
            continue

        seen.add(user_id)
        normalized.append(user_id)

    if not normalized:
        return {}

    return await get_online_status_for_users(normalized)


async def get_last_seen_payload(user_id: int) -> dict | None:
    """
    Return full last seen payload for one user if available.
    """
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return None

    if user_id <= 0:
        return None

    ts = await get_last_seen(user_id)
    if not ts:
        return None

    dt = datetime.fromtimestamp(ts, tz=timezone.utc)

    return {
        "user_id": user_id,
        "is_online": False,
        "last_seen_epoch": ts,
        "last_seen": dt.isoformat(),
        "last_seen_display": timesince(dt, timezone.now()),
    }