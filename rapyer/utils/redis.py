from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager
from typing import TYPE_CHECKING, Any

from redis.asyncio import Redis

from rapyer.context import _context_pipe

if TYPE_CHECKING:
    from rapyer import AtomicRedisModel


def acquire_lock(
    redis: Redis, key: str, sleep_time: float = 0.1
) -> AbstractAsyncContextManager[None]:
    lock_key = f"{key}:lock"
    return redis.lock(lock_key, sleep=sleep_time)


def update_keys_in_pipeline(pipeline_json, redis_key: str, **kwargs):
    for json_path, value in kwargs.items():
        pipeline_json.set(redis_key, json_path, value)


Plan = list[list[str]]


async def execute_load_pipeline(
    redis: Redis,
    classes: list[type["AtomicRedisModel"]],
    keys: list[str],
) -> tuple[Any, list[Plan], list[Any]]:
    """Returns ``(models_dump, plans_per_key, sf_raw_results)``."""
    plans_per_key: list[Plan] = []
    async with redis.pipeline(transaction=True) as pipe:
        pipe.json().mget(keys=keys, path="$")
        for klass, key in zip(classes, keys):
            plan_for_key: Plan = []
            klass.queue_special_loads_in_pipeline(pipe, key, plan_for_key)
            plans_per_key.append(plan_for_key)
        results = await pipe.execute()
    return results[0], plans_per_key, results[1:]


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
