from typing import Callable

from rapyer.base import AtomicRedisModel
from rapyer.types.base import GenericRedisType
from rapyer.types.byte import RedisBytes
from rapyer.types.datetime import RedisDatetimeTimestamp
from rapyer.types.priority_queue import RedisPriorityQueue


def _method_to_tuple(method: Callable) -> tuple[str, str]:
    qualname = method.__qualname__
    class_name, method_name = qualname.rsplit(".", 1)
    return class_name, method_name


def _group(*methods: Callable) -> frozenset[tuple[str, str]]:
    return frozenset(_method_to_tuple(m) for m in methods)


# ── Private helpers: single-underscore internals, not Redis operations ────

PRIVATE_REDIS_TYPE_METHODS = _group(
    # Generic Redis Type
    GenericRedisType.iterate_items,
    # RedisBytes
    RedisBytes._validate_pickle,
    RedisBytes._serialize_pickle,
    # RedisDatetimeTimestamp
    RedisDatetimeTimestamp._validate_timestamp,
    RedisDatetimeTimestamp._serialize_timestamp,
)
PRIVATE_SPECIAL_FIELD_METHODS = _group(
    # RedisPriorityQueue
    RedisPriorityQueue._serialize_value,
    RedisPriorityQueue._deserialize_value,
)
PRIVATE_MODEL_METHODS = _group(
    AtomicRedisModel._search_keys_by_query,
    AtomicRedisModel.acreate_index,
    AtomicRedisModel.adelete_index,
)

PRIVATE_METHODS = (
    PRIVATE_REDIS_TYPE_METHODS | PRIVATE_SPECIAL_FIELD_METHODS | PRIVATE_MODEL_METHODS
)
