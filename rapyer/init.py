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

    # WR-01: the whole unfreeze -> (re)configure -> bake -> refreeze sequence is
    # wrapped so that even if a step raises (e.g. validate_cascade_ttl_targets on
    # a mis-configured graph, or an index ResponseError), every model is refrozen
    # in the finally block. A failed/retried init then never leaves models
    # unfrozen with silently-mutable Meta.ttl / Meta.cascade_ttl.
    try:
        for model in REDIS_MODELS:
            # D-07: unfreeze before this call's ttl (re)assignment — mirrors the
            # D-08 unconditional-reset pattern already used for cascade_ttl below.
            model.Meta._ttl_frozen = False
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
        plan = build_cascade_plan(REDIS_MODELS)
        validate_cascade_ttl_targets(plan)

        # D-05: reuse the single plan build above (no redundant traversal) to
        # stash a per-class predicate that action-boundary methods (refresh_ttl,
        # aset_ttl) branch on at call time — True only for classes with >=1
        # cascade-enabled outgoing edge.
        for model in REDIS_MODELS:
            model._has_cascade = bool(plan[model.__name__].fks)
    finally:
        # D-07: refreeze every model now that the cascade plan is baked against
        # this call's final ttl — forbids further Meta.ttl mutation until the
        # next init_rapyer() call unfreezes it again. Runs even on failure so the
        # freeze invariant always holds.
        for model in REDIS_MODELS:
            model.Meta._ttl_frozen = True

    if redis is not None:
        await register_scripts(redis, is_fake_redis)


async def teardown_rapyer():
    closed_clients = set()
    for model in REDIS_MODELS:
        if id(model.Meta.redis) not in closed_clients:
            closed_clients.add(id(model.Meta.redis))
            await model.Meta.redis.aclose()
        # WR-02: _ttl_frozen is a process-global on the shared per-class Meta
        # singleton, cleared only by init_rapyer(). Reset it on teardown so a
        # torn-down model doesn't leak MetaTtlFrozenError into a later
        # init-less path (or test) that mutates Meta.ttl / Meta.cascade_ttl.
        model.Meta._ttl_frozen = False
