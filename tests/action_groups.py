from typing import Callable

import rapyer
from rapyer import find_redis_models, init_rapyer, teardown_rapyer
from rapyer.base import AtomicRedisModel
from rapyer.types.base import BaseRedisType, GenericRedisType, RedisType
from rapyer.types.byte import RedisBytes
from rapyer.types.datetime import RedisDatetimeTimestamp
from rapyer.types.dct import RedisDict
from rapyer.types.lst import RedisList
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.special import SpecialFieldType


def _method_to_tuple(method: Callable) -> tuple[str, str]:
    qualname = method.__qualname__
    class_name, method_name = qualname.rsplit(".", 1)
    return class_name, method_name


def _group(*methods: Callable) -> frozenset[tuple[str, str]]:
    return frozenset(_method_to_tuple(m) for m in methods)


# ── Private helpers: single-underscore internals, not Redis operations ────
#
# PRIVATE_METHODS — exact match. Only the listed (class, method_name) pair is
# filtered; subclass overrides are NOT auto-filtered.
PRIVATE_METHODS = _group(
    # RedisBytes
    RedisBytes._validate_pickle,
    RedisBytes._serialize_pickle,
    # RedisDatetimeTimestamp
    RedisDatetimeTimestamp._validate_timestamp,
    RedisDatetimeTimestamp._serialize_timestamp,
    # RedisPriorityQueue
    RedisPriorityQueue._serialize_value,
    RedisPriorityQueue._deserialize_value,
    # AtomicRedisModel
    AtomicRedisModel._search_keys_by_query,
    AtomicRedisModel.acreate_index,
    AtomicRedisModel.adelete_index,
)

# PRIVATE_INHERITED_METHODS — MRO-aware. Any subclass that inherits OR
# overrides one of these methods is also filtered. Use this for internal
# helpers whose contract is shared across the type hierarchy
PRIVATE_INHERITED_METHODS = _group(
    BaseRedisType.sub_field_path,
    RedisType.clone,
    RedisType.serialize_unknown,
    RedisType.deserialize_unknown,
    GenericRedisType.iterate_items,
    RedisDict.validate_dict,
    RedisList.create_new_value,
    RedisList.create_new_values,
    SpecialFieldType.clone,
)

# NON_ACTION_METHODS — module-level helpers that aren't Redis actions and
# therefore don't participate in coverage checks.
NON_ACTION_METHODS = _group(
    init_rapyer,
    teardown_rapyer,
    find_redis_models,
)
