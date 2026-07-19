"""Redis cache connection and utilities package.

Public surface:
- init_redis(settings): Initialise Redis connection pool and verify liveness.
- dispose_redis(): Close connections and release resources.
- get_redis(): Yield or return the Redis client instance (DI-ready).
- RedisKeyBuilder: Centralised builder for Redis keys to prevent conflicts.
"""

from cache.client import dispose_redis, get_redis, init_redis
from cache.keys import RedisKeyBuilder

__all__ = [
    "init_redis",
    "dispose_redis",
    "get_redis",
    "RedisKeyBuilder",
]
