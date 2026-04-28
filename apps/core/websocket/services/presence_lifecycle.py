# apps/core/websocket/services/presence_lifecycle.py
# =========================================================
#               Presence Lifecycle Services
# =========================================================

from __future__ import annotations

import time
from datetime import datetime

from django.utils import timezone
from django.utils.timesince import timesince

from apps.core.websocket.services.redis_online_manager import (
    set_user_online,
    set_user_offline,
    get_online_status_for_users,
    get_last_seen,
    get_redis_connection,
)


async def mark_user_online(user_id: int, socket_id: str) -> None:
    """
    Mark a user/socket as online in Redis.
    """
    await set_user_online(user_id, socket_id)


async def mark_user_offline(user_id: int, socket_id: str) -> dict | None:
    """
    Mark a user/socket as offline.

    Returns:
        None -> user is still online on another socket/device
        dict -> fully offline payload with last_seen fields
    """
    await set_user_offline(user_id, socket_id)

    statuses = await get_online_status_for_users([user_id])
    still_online = bool(statuses.get(user_id, False))

    if still_online:
        return None

    ts = await get_last_seen(user_id)
    if not ts:
        ts = int(time.time())
        redis_conn = await get_redis_connection()
        try:
            await redis_conn.set(f"last_seen:{user_id}", ts)
        finally:
            await redis_conn.close()

    dt = datetime.fromtimestamp(ts, tz=timezone.utc)

    return {
        "user_id": int(user_id),
        "is_online": False,
        "last_seen_epoch": int(ts),
        "last_seen": dt.isoformat(),
        "last_seen_display": timesince(dt, timezone.now()),
    }