import logging

import redis.asyncio as redis_async
from redis import ResponseError
from redis.asyncio.client import Redis

from rapyer.base import REDIS_MODELS
from rapyer.cascade import CascadeTTL
from rapyer.cascade.planner import build_cascade_plan, validate_cascade_ttl_targets
from rapyer.result import resolve_forward_refs
from rapyer.scripts import register_scripts
from rapyer.types.relational import resolve_relational_targets


def is_fakeredis(client) -> bool:
    return "fakeredis" in type(client).__module__


async def init_rapyer(
    redis: str | Redis = None,
    ttl: int = None,
    override_old_idx: bool = True,
    prefer_normal_json_dump: bool = None,
    cascade_ttl: CascadeTTL | None = None,
    logger: logging.Logger = None,
):
    if logger is not None:
        rapyer_logger = logging.getLogger("rapyer")
        rapyer_logger.setLevel(logger.level)
        rapyer_logger.handlers.clear()
        for handler in logger.handlers:
            rapyer_logger.addHandler(handler)

    resolve_forward_refs()
    resolve_relational_targets(REDIS_MODELS)

    if isinstance(redis, str):
        redis = redis_async.from_url(redis, decode_responses=True, max_connections=20)

    is_fake_redis = is_fakeredis(redis)

    for model in REDIS_MODELS:
        if redis is not None:
            model.Meta.redis = redis
            model.Meta.is_fake_redis = is_fake_redis
        if ttl is not None:
            model.Meta.ttl = ttl
        if prefer_normal_json_dump is not None:
            model.Meta.prefer_normal_json_dump = prefer_normal_json_dump
        # D-08: cascade_ttl=None is itself a meaningful value ("off"), not
        # "caller didn't pass this" — always reset, unlike ttl/prefer_normal_json_dump.
        model.Meta.cascade_ttl = cascade_ttl

        # Initialize model fields
        model.init_class()

        # Create indexes for models with indexed fields
        if redis is not None:
            fields = model.redis_schema()
            if fields:
                if override_old_idx:
                    try:
                        await model.adelete_index()
                    except ResponseError as e:
                        pass
                try:
                    await model.acreate_index()
                except ResponseError as e:
                    if override_old_idx:
                        raise

    # D-08: fail fast on a mis-configured cascade graph using each model's
    # FINAL per-call Meta.ttl/cascade_ttl (just assigned above), before any
    # script gets registered. Pure config check — needs no Redis connection,
    # runs unconditionally, and is allowed to raise uncaught (matches this
    # file's existing "let startup errors propagate" convention).
    validate_cascade_ttl_targets(build_cascade_plan(REDIS_MODELS))

    if redis is not None:
        await register_scripts(redis, is_fake_redis)


async def teardown_rapyer():
    closed_clients = set()
    for model in REDIS_MODELS:
        if id(model.Meta.redis) not in closed_clients:
            closed_clients.add(id(model.Meta.redis))
            await model.Meta.redis.aclose()
