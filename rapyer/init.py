import logging

import redis.asyncio as redis_async
from redis import ResponseError
from redis.asyncio.client import Redis

from rapyer.base import REDIS_MODELS
from rapyer.cascade import CascadeTTL
from rapyer.cascade.planner import (
    build_cascade_plan,
    cascade_plan_json,
    validate_cascade_ttl_targets,
)
from rapyer.result import resolve_forward_refs
from rapyer.scripts import register_scripts
from rapyer.types.relational import resolve_relational_targets
from rapyer.types.special import CASCADE_PLAN_KEY


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

    # Unfreeze -> (re)configure -> bake -> refreeze, wrapped so a failure mid-way
    # (e.g. a mis-configured graph or an index error) still refreezes every model
    # in the finally block rather than leaving Meta silently mutable.
    try:
        for model in REDIS_MODELS:
            model.Meta._meta_locked = False
            if redis is not None:
                model.Meta.redis = redis
                model.Meta.is_fake_redis = is_fake_redis
            if ttl is not None:
                model.Meta.ttl = ttl
            if prefer_normal_json_dump is not None:
                model.Meta.prefer_normal_json_dump = prefer_normal_json_dump
            # cascade_ttl=None means "off", not "unset", so always reset it —
            # unlike ttl/prefer_normal_json_dump which only apply when passed.
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
                        except ResponseError:
                            pass
                    try:
                        await model.acreate_index()
                    except ResponseError:
                        if override_old_idx:
                            raise

        # Fail fast on a mis-configured cascade graph before any script is
        # registered. Pure config check; needs no Redis connection.
        plan = build_cascade_plan(REDIS_MODELS)
        validate_cascade_ttl_targets(plan)
    finally:
        # Refreeze now that the plan is baked; further Meta mutation is blocked
        # until the next init_rapyer() call. Runs even on failure.
        for model in REDIS_MODELS:
            model.Meta._meta_locked = True

    if redis is not None:
        # Write the full plan to one Redis key so the Lua reads it server-side
        # on every call instead of us reshipping it per call. Must precede
        # register_scripts so the plan is present before any cascade runs.
        await redis.set(CASCADE_PLAN_KEY, cascade_plan_json(plan))
        await register_scripts(redis, is_fake_redis)


async def teardown_rapyer():
    closed_clients = set()
    for model in REDIS_MODELS:
        if id(model.Meta.redis) not in closed_clients:
            closed_clients.add(id(model.Meta.redis))
            await model.Meta.redis.aclose()
        # Clear the freeze on teardown so a torn-down model doesn't leak
        # MetaFrozenError into a later path that mutates Meta without re-init.
        model.Meta._meta_locked = False
