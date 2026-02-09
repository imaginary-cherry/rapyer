"""Redis Pydantic - Pydantic models with Redis as the backend."""

from rapyer.base import (
    AtomicRedisModel,
    aget,
    afind,
    find_redis_models,
    ainsert,
    adelete_many,
    alock_from_key,
    apipeline,
)
from rapyer.init import init_rapyer, teardown_rapyer
from rapyer.result import DeleteResult, RapyerDeleteResult

__all__ = [
    "AtomicRedisModel",
    "init_rapyer",
    "teardown_rapyer",
    "aget",
    "afind",
    "find_redis_models",
    "ainsert",
    "adelete_many",
    "alock_from_key",
    "apipeline",
    "DeleteResult",
    "RapyerDeleteResult",
]
