# services/redis_online_manager.py

import time
import os
import redis.asyncio as redis

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")


ONLINE_USERS_KEY = "online_users"  


# ایجاد اتصال Redis
async def get_redis_connection():
    return redis.from_url(REDIS_URL, decode_responses=True)


# اضافه کردن کاربر به لیست کاربران آنلاین
async def set_user_online(user_id: int, socket_id: str):
    redis_conn = await get_redis_connection()
    
    key = f"online:{user_id}:{socket_id}"
    timestamp = int(time.time())  # زمان ورود

    # تنظیم کلید با expiration برای مدیریت قطع اتصال
    await redis_conn.set(key, timestamp, ex=60)

    # افزودن socket_id به لیست اتصالات کاربر
    await redis_conn.sadd(f"online_users:{user_id}", socket_id)

    await redis_conn.close()


# حذف کاربر از لیست کاربران آنلاین
async def set_user_offline(user_id: int, socket_id: str):
    redis_conn = await get_redis_connection()

    # حذف اتصال فعلی
    await redis_conn.delete(f"online:{user_id}:{socket_id}")
    await redis_conn.srem(f"online_users:{user_id}", socket_id)

    # اگر هیچ اتصالی باقی نمانده → ذخیره آخرین زمان خروج
    remaining = await redis_conn.scard(f"online_users:{user_id}")
    if remaining == 0:
        await redis_conn.set(f"last_seen:{user_id}", int(time.time()))

    await redis_conn.close()
    

# دریافت لیست همه کاربران آنلاین
async def get_all_online_users() -> list:
    redis_conn = await get_redis_connection()
    keys = await redis_conn.keys("online_users:*")
    online = []
    for key in keys:
        user_id = int(key.split(":")[1])
        socket_ids = await redis_conn.smembers(f"online_users:{user_id}")
        has_active = False
        for socket_id in socket_ids:
            if await redis_conn.exists(f"online:{user_id}:{socket_id}"):
                has_active = True
                break
            else:
                await redis_conn.srem(f"online_users:{user_id}", socket_id)
        if has_active:
            online.append(user_id)
        else:
            # مجموعه خالی/بی‌اعتبار؛ پاکش کن تا زامبی نماند
            await redis_conn.delete(f"online_users:{user_id}")
    await redis_conn.close()
    return online




# بررسی وضعیت آنلاین گروهی از کاربران
async def get_online_status_for_users(user_ids: list) -> dict:
    redis_conn = await get_redis_connection()
    result = {}

    for user_id in user_ids:
        socket_ids = await redis_conn.smembers(f"online_users:{user_id}")
        active_sockets = 0

        for socket_id in socket_ids:
            key = f"online:{user_id}:{socket_id}"
            exists = await redis_conn.exists(key)
            if exists:
                active_sockets += 1
            else:
                # سوکت منقضی شده → فقط پاکسازی عضویت
                await redis_conn.srem(f"online_users:{user_id}", socket_id)

        # اگر مجموعه خالی شد، می‌توانی کلید set را هم حذف کنی (اختیاری)
        if active_sockets == 0:
            await redis_conn.delete(f"online_users:{user_id}")

        result[user_id] = active_sockets > 0

    await redis_conn.close()
    return result



async def get_last_seen(user_id: int) -> int | None:
    redis_conn = await get_redis_connection()
    ts = await redis_conn.get(f"last_seen:{user_id}")
    await redis_conn.close()
    return int(ts) if ts else None


# ✅ تمدید اتصال در هنگام دریافت ping (Heartbeat)
async def refresh_user_connection(user_id: int, socket_id: str):
    redis_conn = await get_redis_connection()

    key = f"online:{user_id}:{socket_id}"
    exists = await redis_conn.exists(key)

    if exists:
        await redis_conn.expire(key, 60)
    else:
        is_still_connected = await redis_conn.sismember(f"online_users:{user_id}", socket_id)

        if is_still_connected:
            # 🧠 دوباره کلید را بساز با expire جدید
            await redis_conn.set(key, int(time.time()), ex=60)
        else:
            # ❌ در غیر این صورت، این سوکت معتبر نیست
            await redis_conn.srem(f"online_users:{user_id}", socket_id)

            # بررسی نهایی: اگر هیچ سوکتی باقی نماند → ثبت آفلاین
            remaining = await redis_conn.scard(f"online_users:{user_id}")
            if remaining == 0:
                await redis_conn.set(f"last_seen:{user_id}", int(time.time()))
                # ✅ فقط اینجا می‌توان پیام آفلاین broadcast کرد
                # await broadcast_user_status(user_id, False)  ← در صورت نیاز اضافه کن

    await redis_conn.close()
