"""
Shared method-group definitions for enforcement tests.

Each group is a frozenset of (class_name, method_name) tuples.
Groups are named by the functional nature of the methods they contain.
Each enforcement test composes its exclusion set by taking the union
of the groups it needs.
"""

from typing import Callable

from rapyer.base import AtomicRedisModel
from rapyer.types.base import RedisType
from rapyer.types.byte import RedisBytes
from rapyer.types.datetime import RedisDatetime
from rapyer.types.dct import RedisDict
from rapyer.types.float import RedisFloat
from rapyer.types.integer import RedisInt
from rapyer.types.lst import RedisList
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.special import SpecialFieldType
from rapyer.types.string import RedisStr


def method_to_tuple(method: Callable) -> tuple[str, str]:
    qualname = method.__qualname__
    class_name, method_name = qualname.rsplit(".", 1)
    return class_name, method_name


def _group_rapyer_actions(*methods) -> frozenset[tuple[str, str]]:
    return frozenset(method_to_tuple(m) for m in methods)


# ── Type-level: internal utilities (not Redis operations) ──

TYPE_INTERNAL_METHODS = _group_rapyer_actions(
    RedisType.clone,
    RedisInt.clone,
    RedisFloat.clone,
    RedisStr.clone,
    RedisBytes.clone,
    RedisDatetime.clone,
    RedisList.clone,
    RedisDict.clone,
    RedisList.__init__,
    RedisDict.__init__,
    RedisType.serialize_unknown,
    RedisType.deserialize_unknown,
    RedisList.create_new_value,
    RedisList.create_new_values,
    RedisList.iterate_items,
    RedisList.sub_field_path,
    RedisDict.iterate_items,
    RedisDict.validate_dict,
)

# ── Type-level: operations that return values (read-only or Lua/direct redis) ──

TYPE_READ_METHODS = _group_rapyer_actions(
    RedisType.aload,
    RedisList.apop,
    RedisDict.apop,
    RedisDict.apopitem,
)

# ── Model: data-fetching reads ──

MODEL_READ_METHODS = _group_rapyer_actions(
    AtomicRedisModel.aget,
    AtomicRedisModel.aload,
    AtomicRedisModel.afind,
    AtomicRedisModel.afind_one,
)

# ── Model: lightweight queries that delegate or skip data access ──

MODEL_QUERY_METHODS = _group_rapyer_actions(
    AtomicRedisModel.afind_keys,
    AtomicRedisModel.aexists,
)

MODEL_CHECK_METHODS = _group_rapyer_actions(
    AtomicRedisModel.aexists,
    AtomicRedisModel.afind_keys,
)

# ── Model: update operations ──

MODEL_UPDATE_METHODS = _group_rapyer_actions(
    AtomicRedisModel.aupdate,
)

# ── Model: delete operations ──

MODEL_DELETE_METHODS = _group_rapyer_actions(
    AtomicRedisModel.adelete,
    AtomicRedisModel.adelete_by_key,
    AtomicRedisModel.adelete_many,
)

# ── Model: duplication operations ──

MODEL_DUPLICATE_METHODS = _group_rapyer_actions(
    AtomicRedisModel.aduplicate,
    AtomicRedisModel.aduplicate_many,
)

# ── Model: schema/index operations ──

MODEL_INDEX_METHODS = _group_rapyer_actions(
    AtomicRedisModel.acreate_index,
    AtomicRedisModel.adelete_index,
)

# ── Model: TTL operations (setter + refresh mechanism) ──

MODEL_TTL_METHODS = _group_rapyer_actions(
    AtomicRedisModel.aset_ttl,
    AtomicRedisModel.refresh_ttl_if_needed,
    RedisType.refresh_ttl_if_needed,
)

# ── Model: internal query helpers ──

MODEL_INTERNAL_METHODS = _group_rapyer_actions(
    AtomicRedisModel._search_keys_by_query,
)

# ── Priority queue: read-only operations ──

PQ_READ_METHODS = _group_rapyer_actions(
    RedisPriorityQueue.apeek,
    RedisPriorityQueue.asize,
    RedisPriorityQueue.aitems,
)

# ── Special field lifecycle methods (abstract + concrete) ──

SPECIAL_FIELD_LIFECYCLE_METHODS = _group_rapyer_actions(
    SpecialFieldType.asave_special,
    SpecialFieldType.adelete_special,
    RedisPriorityQueue.asave_special,
    RedisPriorityQueue.adelete_special,
)
