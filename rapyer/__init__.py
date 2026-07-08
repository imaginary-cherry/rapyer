"""Redis Pydantic - Pydantic models with Redis as the backend."""

from rapyer.base import (
    AtomicRedisModel,
    adelete_many,
    aexists,
    afind,
    afind_one,
    aget,
    aget_or_create,
    ainsert,
    alock_from_key,
    apipeline,
    find_redis_models,
)
from rapyer.init import init_rapyer, teardown_rapyer
from rapyer.result import (
    DeleteResult,
    GetOrCreateResult,
    GetOrCreateStatus,
    RapyerDeleteResult,
    resolve_forward_refs as _resolve_forward_refs,
)

# AtomicRedisModel is now imported so the forward refs in result.py can resolve.
_resolve_forward_refs()

__all__ = [
    "AtomicRedisModel",
    "init_rapyer",
    "teardown_rapyer",
    "aexists",
    "aget",
    "aget_or_create",
    "afind",
    "afind_one",
    "find_redis_models",
    "ainsert",
    "adelete_many",
    "alock_from_key",
    "apipeline",
    "DeleteResult",
    "GetOrCreateResult",
    "GetOrCreateStatus",
    "RapyerDeleteResult",
]
