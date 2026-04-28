# apps/core/websocket/services/presence_watchdog.py
# =========================================================
#                  Presence Watchdog
# =========================================================

from __future__ import annotations

import asyncio
import logging
import time

from apps.core.websocket.services.redis_online_manager import get_redis_connection
from apps.core.websocket.services.presence_lifecycle import mark_user_offline
from apps.core.websocket.services.presence_broadcast import (
    broadcast_user_online_status,
    broadcast_user_last_seen,
)

logger = logging.getLogger(__name__)

_LOCK_KEY = "presence_watchdog_lock"
_LOCK_TTL = 20  # seconds
_TICK = 10      # seconds

_task: asyncio.Task | None = None


# ---------------------------------------------------------
# Cleanup ghost sockets and detect offline transitions
# ---------------------------------------------------------
async def _cleanup_and_detect_transitions():
    """
    Scan Redis presence sets, remove ghost sockets,
    and broadcast offline transitions only when a user
    becomes fully offline.
    """
    redis_conn = await get_redis_connection()

    try:
        async for key in redis_conn.scan_iter(match="online_users:*"):
            try:
                _, raw_user_id = key.split(":", 1)
                user_id = int(raw_user_id)
            except Exception:
                logger.warning(f"[PresenceWatchdog] Invalid key format: {key}")
                continue

            try:
                socket_ids = await redis_conn.smembers(key)
            except Exception as exc:
                logger.error(
                    f"[PresenceWatchdog] Failed to read socket set for user {user_id}: {exc}",
                    exc_info=True,
                )
                continue

            stale_socket_ids: list[str] = []

            for socket_id in list(socket_ids):
                try:
                    exists = await redis_conn.exists(f"online:{user_id}:{socket_id}")
                except Exception as exc:
                    logger.error(
                        f"[PresenceWatchdog] Failed to check socket key for user {user_id}, socket {socket_id}: {exc}",
                        exc_info=True,
                    )
                    continue

                if not exists:
                    stale_socket_ids.append(socket_id)

            for socket_id in stale_socket_ids:
                try:
                    payload = await mark_user_offline(user_id, socket_id)
                except Exception as exc:
                    logger.error(
                        f"[PresenceWatchdog] mark_user_offline failed for user {user_id}, socket {socket_id}: {exc}",
                        exc_info=True,
                    )
                    continue

                if payload is not None:
                    try:
                        await broadcast_user_online_status(user_id, False)
                        await broadcast_user_last_seen(user_id, payload)
                    except Exception as exc:
                        logger.error(
                            f"[PresenceWatchdog] Offline broadcast failed for user {user_id}: {exc}",
                            exc_info=True,
                        )

    finally:
        try:
            await redis_conn.close()
        except Exception:
            pass


# ---------------------------------------------------------
# Main watchdog loop
# ---------------------------------------------------------
async def _watchdog_loop():
    """
    Singleton watchdog loop with Redis lock protection.
    """
    while True:
        redis_conn = await get_redis_connection()

        try:
            ok = await redis_conn.set(
                _LOCK_KEY,
                str(time.time()),
                nx=True,
                ex=_LOCK_TTL,
            )

            if not ok:
                await asyncio.sleep(_TICK)
                continue

            logger.info("[PresenceWatchdog] Lock acquired")

            while True:
                try:
                    await redis_conn.expire(_LOCK_KEY, _LOCK_TTL)
                    await _cleanup_and_detect_transitions()
                    await asyncio.sleep(_TICK)

                except asyncio.CancelledError:
                    logger.info("[PresenceWatchdog] Loop cancelled")
                    return

                except Exception as exc:
                    logger.error(
                        f"[PresenceWatchdog] Loop iteration failed: {exc}",
                        exc_info=True,
                    )
                    await asyncio.sleep(_TICK)

        except asyncio.CancelledError:
            logger.info("[PresenceWatchdog] Task cancelled")
            return

        except Exception as exc:
            logger.error(
                f"[PresenceWatchdog] Top-level loop error: {exc}",
                exc_info=True,
            )
            await asyncio.sleep(_TICK)

        finally:
            try:
                await redis_conn.close()
            except Exception:
                pass


# ---------------------------------------------------------
# Public bootstrap
# ---------------------------------------------------------
def ensure_presence_watchdog_running():
    """
    Start the presence watchdog once per process.

    Safe to call multiple times.
    Must be called only when an event loop is available.
    """
    global _task

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    if _task and not _task.done():
        return

    _task = loop.create_task(_watchdog_loop())
    logger.info("[PresenceWatchdog] Task started")