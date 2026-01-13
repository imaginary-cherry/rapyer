from contextlib import AbstractAsyncContextManager

from redis.asyncio import Redis


def acquire_lock(
    redis: Redis, key: str, sleep_time: int = 0.1
) -> AbstractAsyncContextManager[None]:
    lock_key = f"{key}:lock"
    return redis.lock(lock_key, sleep=sleep_time)


def update_keys_in_pipeline(pipeline, redis_key: str, **kwargs):
    for json_path, value in kwargs.items():
        pipeline.json().set(redis_key, json_path, value)


async def refresh_ttl_if_needed(
    redis_client: Redis, key: str, ttl: int | None, refresh_ttl: bool = True
) -> None:
    if ttl is not None and refresh_ttl:
        await redis_client.expire(key, ttl)
