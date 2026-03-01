from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager

from redis.asyncio import Redis

from rapyer.context import _context_pipe


def acquire_lock(
    redis: Redis, key: str, sleep_time: int = 0.1
) -> AbstractAsyncContextManager[None]:
    lock_key = f"{key}:lock"
    return redis.lock(lock_key, sleep=sleep_time)


def update_keys_in_pipeline(pipeline, redis_key: str, **kwargs):
    for json_path, value in kwargs.items():
        pipeline.json().set(redis_key, json_path, value)


async def batched(iterable, n):
    for i in range(0, len(iterable), n):
        yield iterable[i : i + n]


async def execute_delete_batch(redis: Redis, keys: list[str]) -> int:
    async with redis.pipeline(transaction=True) as pipe:
        pipe.delete(*keys)
        results = await pipe.execute()
    return sum(results)


async def scan_keys(redis: Redis, pattern: str, max_results: int) -> list[str]:
    keys: list[str] = []
    cursor = 0
    while len(keys) < max_results:
        cursor, batch = await redis.scan(
            cursor=cursor, match=pattern, count=max_results - len(keys)
        )
        keys.extend(batch[: max_results - len(keys)])
        if cursor == 0:
            break
    return keys


async def delete_in_batches(
    redis: Redis, batch_iterator: AsyncIterator[list[str]]
) -> tuple[int, bool]:
    client = _context_pipe.get()
    if client is not None:
        count = 0
        async for batch in batch_iterator:
            client.delete(*batch)
            count += len(batch)
        return count, False

    total = 0
    async for batch in batch_iterator:
        total += await execute_delete_batch(redis, batch)
    return total, True
