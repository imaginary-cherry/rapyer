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
from rapyer.embeddings.adapter import default_embedding_adapter
from rapyer.embeddings.protocol import EmbeddingAdapter
from rapyer.errors import RedisTextRealRedisRequiredError, VectorDimMismatchError
from rapyer.result import resolve_forward_refs
from rapyer.scripts import register_cascade_function, register_scripts
from rapyer.types.relational import resolve_relational_targets
from rapyer.types.text import RedisText
from rapyer.utils.annotation import annotation_origin
from rapyer.utils.pythonic import safe_issubclass


def is_fakeredis(client) -> bool:
    return "fakeredis" in type(client).__module__


def _model_has_redis_text_field(model_cls, seen: set | None = None) -> bool:
    seen = seen or set()
    if model_cls in seen:
        return False
    seen = seen | {model_cls}
    for field_name in model_cls._special_field_names:
        annotation = model_cls.model_fields[field_name].annotation
        if safe_issubclass(annotation_origin(annotation), RedisText):
            return True
    for field_name in model_cls._contain_sf:
        annotation = model_cls.model_fields[field_name].annotation
        nested_cls = annotation_origin(annotation)
        if _model_has_redis_text_field(nested_cls, seen):
            return True
    return False


async def init_rapyer(
    redis: str | Redis = None,
    ttl: int = None,
    override_old_idx: bool = True,
    prefer_normal_json_dump: bool = None,
    cascade_ttl: CascadeTTL | None = None,
    logger: logging.Logger = None,
    vectorizer: EmbeddingAdapter | None = None,
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

    # Build the fallback default once so non-preset models share one adapter (one model load).
    default_vectorizer = vectorizer or default_embedding_adapter()

    # Unfreeze -> (re)configure -> bake -> refreeze; finally always refreezes, even on failure.
    try:
        for model in REDIS_MODELS:
            model.Meta._meta_locked = False
            if redis is not None:
                model.Meta.redis = redis
                model.Meta.is_fake_redis = is_fake_redis
                # RedisText is unsupported on fakeredis; fail fast instead of a silent no-op.
                if is_fake_redis and _model_has_redis_text_field(model):
                    raise RedisTextRealRedisRequiredError(model.__name__)
            if ttl is not None:
                model.Meta.ttl = ttl
            if prefer_normal_json_dump is not None:
                model.Meta.prefer_normal_json_dump = prefer_normal_json_dump
            # cascade_ttl=None means "off" not "unset", so always reset it (unlike ttl above).
            model.Meta.cascade_ttl = cascade_ttl
            # Unlike cascade_ttl, a per-model preset (D-06) beats this global param/default.
            if not model.Meta._vectorizer_preset:
                model.Meta._resolve_vectorizer(default_vectorizer)

            # A declared Vector(dim=N) must match the now-resolved vectorizer's dims (D-03).
            for field_name, vector_annotation in model._vector_fields.items():
                if vector_annotation.dim != model.Meta.vectorizer.dims:
                    raise VectorDimMismatchError(
                        field_name, vector_annotation.dim, model.Meta.vectorizer.dims
                    )

            # Initialize model fields
            model.init_class()

        # Index creation runs only after every model is rebound, so an index error leaves none unbound.
        for model in REDIS_MODELS:
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

        # Fail fast on a mis-configured cascade graph before any script is registered.
        plan = build_cascade_plan(REDIS_MODELS)
        validate_cascade_ttl_targets(plan)
    finally:
        # Refreeze now that the plan is baked; blocks further mutation until the next init_rapyer().
        for model in REDIS_MODELS:
            model.Meta._meta_locked = True

    if redis is not None:
        await register_scripts(redis, is_fake_redis)
        # TTL cascade traversal is real-Redis-7+-only; on fakeredis only root-own keys refresh.
        if not is_fake_redis:
            # Assigned post-freeze: cascade_function_name is a freeze-exempt derived value.
            function_name = await register_cascade_function(
                redis, cascade_plan_json(plan)
            )
            for model in REDIS_MODELS:
                model.Meta.cascade_function_name = function_name


async def teardown_rapyer():
    closed_clients = set()
    for model in REDIS_MODELS:
        if id(model.Meta.redis) not in closed_clients:
            closed_clients.add(id(model.Meta.redis))
            await model.Meta.redis.aclose()
        # Clears the freeze so a torn-down model doesn't leak MetaFrozenError before the next re-init.
        model.Meta._meta_locked = False
