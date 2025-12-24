# services/presence_watchdog.py
import asyncio
import time
from datetime import datetime

from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer
from django.utils import timezone
from django.utils.timesince import timesince

from apps.conversation.models import Dialogue
from services.redis_online_manager import get_redis_connection, get_last_seen

_LOCK_KEY = "presence_watchdog_lock"
_LOCK_TTL = 20  # seconds
_TICK = 10      # seconds

_task = None

async def _broadcast_user_offline(user_id: int):
    # Fetch dialogue slugs for this user (only on transition)
    slugs = await sync_to_async(list)(
        Dialogue.objects.filter(participants__id=user_id).values_list("slug", flat=True)
    )

    # Ensure last_seen
    ts = await get_last_seen(user_id)
    if not ts:
        ts = int(time.time())

    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    iso = dt.isoformat()
    disp = timesince(dt)

    channel_layer = get_channel_layer()

    for slug in slugs:
        group = f"dialogue_{slug}"

        # Presence offline
        await channel_layer.group_send(
            group,
            {
                "type": "dispatch_event",
                "app": "conversation",
                "event": "user_online_status",
                "data": {
                    "dialogue_slug": slug,
                    "user_id": user_id,
                    "is_online": False,
                },
            },
        )

        # Last seen
        await channel_layer.group_send(
            group,
            {
                "type": "dispatch_event",
                "app": "conversation",
                "event": "user_last_seen",
                "data": {
                    "dialogue_slug": slug,
                    "user_id": user_id,
                    "is_online": False,
                    "last_seen_epoch": ts,
                    "last_seen": iso,
                    "last_seen_display": disp,
                },
            },
        )

async def _cleanup_and_detect_transitions():
    """
    One watchdog tick:
    - remove ghost sockets (missing online:{user}:{socket})
    - detect fully-offline transitions and broadcast
    """
    r = await get_redis_connection()
    try:
        # Iterate users without blocking Redis (SCAN instead of KEYS)
        async for key in r.scan_iter(match="online_users:*"):
            # key = online_users:{user_id}
            try:
                user_id = int(key.split(":")[1])
            except Exception:
                continue

            socket_ids = await r.smembers(key)
            active = 0

            for sid in list(socket_ids):
                if await r.exists(f"online:{user_id}:{sid}"):
                    active += 1
                else:
                    # Remove ghost sid
                    await r.srem(key, sid)

            # Fully offline
            if active == 0:
                # If set is empty => cleanup
                await r.delete(key)

                # Store last_seen (only once)
                await r.set(f"last_seen:{user_id}", int(time.time()))

                # Broadcast offline (transition-safe enough)
                await _broadcast_user_offline(user_id)

    finally:
        await r.close()

async def _watchdog_loop():
    """
    Leader-elected watchdog using Redis lock.
    """
    while True:
        r = await get_redis_connection()
        try:
            # Acquire lock (single leader per cluster)
            ok = await r.set(_LOCK_KEY, str(time.time()), nx=True, ex=_LOCK_TTL)
            if not ok:
                await asyncio.sleep(_TICK)
                continue

            # Leader loop
            while True:
                # Extend lock
                await r.expire(_LOCK_KEY, _LOCK_TTL)

                # Run one tick
                await _cleanup_and_detect_transitions()

                await asyncio.sleep(_TICK)

        except asyncio.CancelledError:
            return
        except Exception:
            # Prevent crash loop
            await asyncio.sleep(_TICK)
        finally:
            try:
                await r.close()
            except Exception:
                pass

def ensure_presence_watchdog_running():
    """
    Safe starter from ASGI import time.
    """
    global _task
    if _task and not _task.done():
        return

    loop = asyncio.get_event_loop()
    _task = loop.create_task(_watchdog_loop())
