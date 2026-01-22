import logging

import redis.asyncio as redis_async
from redis import ResponseError
from redis.asyncio.client import Redis

from rapyer.base import REDIS_MODELS
from rapyer.scripts import register_scripts


def is_fakeredis(client) -> bool:
    return "fakeredis" in type(client).__module__


async def init_rapyer(
    redis: str | Redis = None,
    ttl: int = None,
    override_old_idx: bool = True,
    prefer_normal_json_dump: bool = None,
    logger: logging.Logger = None,
):
    if logger is not None:
        rapyer_logger = logging.getLogger("rapyer")
        rapyer_logger.setLevel(logger.level)
        rapyer_logger.handlers.clear()
        for handler in logger.handlers:
            rapyer_logger.addHandler(handler)

    if isinstance(redis, str):
        redis = redis_async.from_url(redis, decode_responses=True, max_connections=20)

    is_fake_redis = is_fakeredis(redis)
    if redis is not None:
        await register_scripts(redis, is_fake_redis)

    for model in REDIS_MODELS:
        if redis is not None:
            model.Meta.redis = redis
            model.Meta.is_fake_redis = is_fake_redis
        if ttl is not None:
            model.Meta.ttl = ttl
        if prefer_normal_json_dump is not None:
            model.Meta.prefer_normal_json_dump = prefer_normal_json_dump

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


async def teardown_rapyer():
    closed_clients = set()
    for model in REDIS_MODELS:
        if id(model.Meta.redis) not in closed_clients:
            closed_clients.add(id(model.Meta.redis))
            await model.Meta.redis.aclose()
