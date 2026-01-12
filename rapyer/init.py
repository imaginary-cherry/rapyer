import redis.asyncio as redis_async
from redis import ResponseError
from redis.asyncio.client import Redis

from rapyer.base import REDIS_MODELS


async def init_rapyer(
    redis: str | Redis = None, ttl: int = None, override_old_idx: bool = True
):
    if isinstance(redis, str):
        redis = redis_async.from_url(redis, decode_responses=True, max_connections=20)

    for model in REDIS_MODELS:
        if redis is not None:
            model.Meta.redis = redis
        if ttl is not None:
            model.Meta.ttl = ttl

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
