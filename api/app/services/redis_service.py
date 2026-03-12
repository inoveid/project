"""
Redis connection pool — singleton for the application lifecycle.

Provides async Redis client via redis.asyncio.
Initialized in app lifespan, closed on shutdown.
"""
from __future__ import annotations

import logging

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None


async def init_redis() -> aioredis.Redis:
    """Create and store a Redis connection pool. Call once in app lifespan."""
    global _redis
    _redis = aioredis.from_url(
        settings.redis_url,
        decode_responses=True,
        max_connections=20,
    )
    # Verify connectivity
    await _redis.ping()
    logger.info("Redis connected: %s", settings.redis_url)
    return _redis


async def close_redis() -> None:
    """Close the Redis connection pool. Call on app shutdown."""
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None
        logger.info("Redis connection closed")


def get_redis() -> aioredis.Redis:
    """Get the active Redis client. Raises if not initialized."""
    if _redis is None:
        raise RuntimeError("Redis not initialized. Call init_redis() in app lifespan.")
    return _redis
