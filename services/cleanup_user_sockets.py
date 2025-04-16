import redis.asyncio as redis
import asyncio
from django.conf import settings

REDIS_URL = getattr(settings, "REDIS_URL", "redis://127.0.0.1:6379/0")

async def cleanup_expired_sockets():
    redis_conn = redis.from_url(REDIS_URL, decode_responses=True)
    keys = await redis_conn.keys("online_users:*")
    
    for key in keys:
        user_id = key.split(":")[1]
        socket_ids = await redis_conn.smembers(key)
        for socket_id in socket_ids:
            if not await redis_conn.exists(f"online:{user_id}:{socket_id}"):
                await redis_conn.srem(key, socket_id)
    
    await redis_conn.close()

# فقط برای تست دستی:
if __name__ == "__main__":
    asyncio.run(cleanup_expired_sockets())
    
    
# بعدا باید تکمیل شود برای نمایش تعداد دیوایسهای متصل به یک اکانت و IP آنها