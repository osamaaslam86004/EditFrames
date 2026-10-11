# config/cache.py

import redis.asyncio as aioredis
from core.config import get_settings

_redis_client: aioredis.Redis | None = None

settings = get_settings()


async def get_redis_client() -> aioredis.Redis:
    """
    Returns an async Redis client instance bound to the current running event loop.
    """
    global _redis_client

    if _redis_client is None:

        _redis_client = aioredis.from_url(
            settings.redis.async_url,
            decode_responses=True,
            socket_connect_timeout=settings.redis.socket_connect_timeout,
            socket_timeout=settings.redis.socket_timeout,
        )
    return _redis_client


async def close_redis() -> None:
    """
    Closes the Redis pool connections and resets the global instance.
    Prevents 'Event loop is closed' runtime errors between Celery task runs.
    """
    global _redis_client

    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
