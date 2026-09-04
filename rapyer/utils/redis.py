from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager
from typing import TYPE_CHECKING, Any

from redis.asyncio import Redis

from rapyer.context import _context_pipe
from rapyer.errors import KeyNotFound
from rapyer.utils.pythonic import inject_at_paths

if TYPE_CHECKING:
    from rapyer import AtomicRedisModel
    from rapyer.config import RedisConfig


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
    meta: "RedisConfig",
    classes: list[type["AtomicRedisModel"]],
    keys: list[str],
) -> tuple[Any, list[Plan], list[Any]]:
    """Returns ``(models_dump, plans_per_key, sf_raw_results)``."""
    plans_per_key: list[Plan] = []
    async with meta.redis.pipeline(transaction=True) as pipe:
        pipe.json().mget(keys=keys, path="$")
        for klass, key in zip(classes, keys):
            plan_for_key: Plan = []
            klass.queue_special_loads_in_pipeline(pipe, key, plan_for_key)
            plans_per_key.append(plan_for_key)
        results = await pipe.execute()
    return results[0], plans_per_key, results[1:]


async def fetch_models_with_sf_loads(
    meta: "RedisConfig",
    classes: list[type["AtomicRedisModel"]],
    keys: list[str],
) -> tuple[Any, list[Plan], list[Any]]:
    """
    Fetch model dumps for ``keys`` plus any nested-SF loads. Uses the
    transaction pipeline when any class has SF; otherwise a direct ``JSON.MGET``.
    Returns ``(models_dump, plans_per_key, sf_raw_results)``.
    """
    if any(c.contains_sf_field() for c in classes):
        return await execute_load_pipeline(meta, classes, keys)
    models = await meta.redis_json.mget(keys=keys, path="$")
    return models, [[] for _ in keys], []


def build_models_from_dumps(
    models_dump: list,
    classes: list[type["AtomicRedisModel"]],
    keys: list[str],
    plans_per_key: list[Plan],
    sf_raw: list,
    raise_on_missing: bool,
) -> list:
    """
    Walk the per-key (model_dump, plan) pairs from a load pipeline, slice
    ``sf_raw`` by plan length, inject the special-field data into each dump,
    and call ``create_redis_model``. Missing entries raise ``KeyNotFound``
    when ``raise_on_missing`` is True; otherwise they are skipped.
    """
    instances: list = []
    cursor = 0
    for data, key, klass, key_plan in zip(models_dump, keys, classes, plans_per_key):
        slice_end = cursor + len(key_plan)
        raw_slice = sf_raw[cursor:slice_end]
        cursor = slice_end
        # Real redis returns None for a missing key; fakeredis returns [].
        if not data:
            if raise_on_missing:
                raise KeyNotFound(f"{key} is missing in redis")
            continue
        if isinstance(data, list):
            data = data[0]
        inject_at_paths(data, key_plan, raw_slice)
        model = klass.create_redis_model(data, key)
        if model is None:
            continue
        instances.append(model)
    return instances


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
