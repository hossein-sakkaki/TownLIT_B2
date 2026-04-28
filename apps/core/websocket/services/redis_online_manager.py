# services/redis_online_manager.py
import os
import time

import redis.asyncio as redis

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")


# Redis connection ------------------------------------------
async def get_redis_connection():
    return redis.from_url(REDIS_URL, decode_responses=True)


# Online user management ------------------------------------
async def set_user_online(user_id: int, socket_id: str):
    redis_conn = await get_redis_connection()
    try:
        key = f"online:{user_id}:{socket_id}"
        await redis_conn.set(key, int(time.time()), ex=60)
        await redis_conn.sadd(f"online_users:{user_id}", socket_id)
    finally:
        await redis_conn.close()


# Offline user management -----------------------------------
async def set_user_offline(user_id: int, socket_id: str):
    redis_conn = await get_redis_connection()
    try:
        await redis_conn.delete(f"online:{user_id}:{socket_id}")
        await redis_conn.srem(f"online_users:{user_id}", socket_id)

        remaining = await redis_conn.scard(f"online_users:{user_id}")
        if remaining == 0:
            await redis_conn.set(f"last_seen:{user_id}", int(time.time()))
            await redis_conn.delete(f"online_users:{user_id}")
    finally:
        await redis_conn.close()


# Online user list ------------------------------------------
async def get_all_online_users() -> list[int]:
    redis_conn = await get_redis_connection()
    online: list[int] = []

    try:
        async for key in redis_conn.scan_iter(match="online_users:*"):
            try:
                _, raw_user_id = key.split(":", 1)
                user_id = int(raw_user_id)
            except Exception:
                continue

            socket_ids = await redis_conn.smembers(f"online_users:{user_id}")

            has_active = False
            for socket_id in list(socket_ids):
                if await redis_conn.exists(f"online:{user_id}:{socket_id}"):
                    has_active = True
                else:
                    await redis_conn.srem(f"online_users:{user_id}", socket_id)

            if has_active:
                online.append(user_id)
            else:
                await redis_conn.delete(f"online_users:{user_id}")

        return online

    finally:
        await redis_conn.close()


# Online status for multiple users --------------------------
async def get_online_status_for_users(user_ids: list[int]) -> dict[int, bool]:
    redis_conn = await get_redis_connection()
    result: dict[int, bool] = {}

    try:
        for user_id in user_ids:
            socket_ids = await redis_conn.smembers(f"online_users:{user_id}")
            active_sockets = 0

            for socket_id in list(socket_ids):
                key = f"online:{user_id}:{socket_id}"
                if await redis_conn.exists(key):
                    active_sockets += 1
                else:
                    await redis_conn.srem(f"online_users:{user_id}", socket_id)

            if active_sockets == 0:
                await redis_conn.delete(f"online_users:{user_id}")

            result[int(user_id)] = active_sockets > 0

        return result

    finally:
        await redis_conn.close()


# Last seen timestamp ---------------------------------------
async def get_last_seen(user_id: int) -> int | None:
    redis_conn = await get_redis_connection()
    try:
        ts = await redis_conn.get(f"last_seen:{user_id}")
        return int(ts) if ts else None
    finally:
        await redis_conn.close()


# Refresh user connection -----------------------------------
async def refresh_user_connection(user_id: int, socket_id: str):
    """
    Refresh TTL for an existing live socket.

    Important:
    - Do not resurrect expired keys.
    - If key is missing, treat socket as ghost and clean it.
    """
    redis_conn = await get_redis_connection()
    try:
        key = f"online:{user_id}:{socket_id}"

        if await redis_conn.exists(key):
            await redis_conn.expire(key, 60)
            return

        await redis_conn.srem(f"online_users:{user_id}", socket_id)

        remaining = await redis_conn.scard(f"online_users:{user_id}")
        if remaining == 0:
            await redis_conn.set(f"last_seen:{user_id}", int(time.time()))
            await redis_conn.delete(f"online_users:{user_id}")

    finally:
        await redis_conn.close()