from typing import Callable

from rapyer.base import AtomicRedisModel
from rapyer.types.base import GenericRedisType, RedisType
from rapyer.types.byte import RedisBytes
from rapyer.types.datetime import RedisDatetime, RedisDatetimeTimestamp
from rapyer.types.dct import RedisDict
from rapyer.types.float import RedisFloat
from rapyer.types.integer import RedisInt
from rapyer.types.lst import RedisList
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.special import SpecialFieldType
from rapyer.types.string import RedisStr


def _method_to_tuple(method: Callable) -> tuple[str, str]:
    qualname = method.__qualname__
    class_name, method_name = qualname.rsplit(".", 1)
    return class_name, method_name


def _group(*methods: Callable) -> frozenset[tuple[str, str]]:
    return frozenset(_method_to_tuple(m) for m in methods)


# ── Private helpers: single-underscore internals, not Redis operations ────

PRIVATE_REDIS_TYPE_METHODS = _group(
    # Generic Redis Type: iterate_items implementations
    GenericRedisType.iterate_items,
    RedisDict.iterate_items,
    RedisList.iterate_items,

    # clone implementations — internal helpers, not Redis operations
    RedisType.clone,
    RedisBytes.clone,
    RedisStr.clone,
    RedisFloat.clone,
    RedisInt.clone,
    RedisDatetime.clone,
    RedisDict.clone,
    RedisList.clone,
    # RedisBytes
    RedisBytes._validate_pickle,
    RedisBytes._serialize_pickle,
    # RedisDatetimeTimestamp
    RedisDatetimeTimestamp._validate_timestamp,
    RedisDatetimeTimestamp._serialize_timestamp,
)
PRIVATE_SPECIAL_FIELD_METHODS = _group(
    # clone implementations — internal helpers, not Redis operations
    SpecialFieldType.clone,
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
