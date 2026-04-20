from typing import Callable

from rapyer.base import AtomicRedisModel
from rapyer.types.base import RedisType
from rapyer.types.byte import RedisBytes
from rapyer.types.datetime import RedisDatetime, RedisDatetimeTimestamp
from rapyer.types.dct import RedisDict
from rapyer.types.float import RedisFloat
from rapyer.types.integer import RedisInt
from rapyer.types.lst import RedisList
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.string import RedisStr


def _method_to_tuple(method: Callable) -> tuple[str, str]:
    qualname = method.__qualname__
    class_name, method_name = qualname.rsplit(".", 1)
    return class_name, method_name


def _group(*methods: Callable) -> frozenset[tuple[str, str]]:
    return frozenset(_method_to_tuple(m) for m in methods)


# ── ActionGroup.READ ──────────────────────────────────────────────────────

READ_REDIS_TYPE_METHODS = _group(
    # RedisType (base)
    RedisType.aload,
)
READ_SPECIAL_FIELD_METHODS = _group()
READ_MODEL_METHODS = _group()

READ_METHODS = READ_REDIS_TYPE_METHODS | READ_SPECIAL_FIELD_METHODS | READ_MODEL_METHODS


# ── ActionGroup.UPDATE ────────────────────────────────────────────────────

UPDATE_REDIS_TYPE_METHODS = _group(
    # RedisList
    RedisList.__setitem__,
    RedisList.__iadd__,
    RedisList.append,
    RedisList.extend,
    RedisList.insert,
    RedisList.clear,
    RedisList.remove_range,
    RedisList.aappend,
    RedisList.aextend,
    RedisList.apop,
    RedisList.ainsert,
    RedisList.aclear,
    # RedisDict
    RedisDict.update,
    RedisDict.clear,
    RedisDict.__setitem__,
    RedisDict.aset_item,
    RedisDict.adel_item,
    RedisDict.aupdate,
    RedisDict.apop,
    RedisDict.apopitem,
    RedisDict.aclear,
    # RedisInt
    RedisInt.aincrease,
    RedisInt.__iadd__,
    RedisInt.__isub__,
    RedisInt.__imul__,
    RedisInt.__ifloordiv__,
    RedisInt.__imod__,
    RedisInt.__ipow__,
    # RedisFloat
    RedisFloat.aincrease,
    RedisFloat.__iadd__,
    RedisFloat.__isub__,
    RedisFloat.__imul__,
    RedisFloat.__itruediv__,
    RedisFloat.__ifloordiv__,
    RedisFloat.__imod__,
    RedisFloat.__ipow__,
    # RedisStr
    RedisStr.__iadd__,
    RedisStr.__imul__,
    # RedisBytes
    RedisBytes.__iadd__,
    # RedisDatetime
    RedisDatetime.__iadd__,
    RedisDatetime.__isub__,
    # RedisDatetimeTimestamp
    RedisDatetimeTimestamp.__iadd__,
    RedisDatetimeTimestamp.__isub__,
)
UPDATE_SPECIAL_FIELD_METHODS = _group(
    # RedisPriorityQueue
    RedisPriorityQueue.apush,
    RedisPriorityQueue.apush_many,
    RedisPriorityQueue.apop,
    RedisPriorityQueue.aclear,
    RedisPriorityQueue.aremove,
)
UPDATE_MODEL_METHODS = _group()

UPDATE_METHODS = (
    UPDATE_REDIS_TYPE_METHODS | UPDATE_SPECIAL_FIELD_METHODS | UPDATE_MODEL_METHODS
)


# ── ActionGroup.APPEND ────────────────────────────────────────────────────

APPEND_REDIS_TYPE_METHODS = _group(
    # RedisList
    RedisList.__iadd__,
    RedisList.append,
    RedisList.extend,
    RedisList.insert,
    RedisList.aappend,
    RedisList.aextend,
    RedisList.ainsert,
    # RedisStr
    RedisStr.__iadd__,
    # RedisBytes
    RedisBytes.__iadd__,
)
APPEND_SPECIAL_FIELD_METHODS = _group(
    # RedisPriorityQueue
    RedisPriorityQueue.apush,
    RedisPriorityQueue.apush_many,
)
APPEND_MODEL_METHODS = _group()

APPEND_METHODS = (
    APPEND_REDIS_TYPE_METHODS | APPEND_SPECIAL_FIELD_METHODS | APPEND_MODEL_METHODS
)


# ── ActionGroup.DELETE ────────────────────────────────────────────────────

DELETE_REDIS_TYPE_METHODS = _group(
    # RedisList
    RedisList.clear,
    RedisList.remove_range,
    RedisList.apop,
    RedisList.aclear,
    # RedisDict
    RedisDict.clear,
    RedisDict.adel_item,
    RedisDict.apop,
    RedisDict.apopitem,
    RedisDict.aclear,
)
DELETE_SPECIAL_FIELD_METHODS = _group(
    # RedisPriorityQueue
    RedisPriorityQueue.apop,
    RedisPriorityQueue.aclear,
    RedisPriorityQueue.aremove,
)
DELETE_MODEL_METHODS = _group()

DELETE_METHODS = (
    DELETE_REDIS_TYPE_METHODS | DELETE_SPECIAL_FIELD_METHODS | DELETE_MODEL_METHODS
)


# ── ActionGroup.ARITHMETIC ────────────────────────────────────────────────

ARITHMETIC_REDIS_TYPE_METHODS = _group(
    # RedisInt
    RedisInt.aincrease,
    RedisInt.__iadd__,
    RedisInt.__isub__,
    RedisInt.__imul__,
    RedisInt.__ifloordiv__,
    RedisInt.__imod__,
    RedisInt.__ipow__,
    # RedisFloat
    RedisFloat.aincrease,
    RedisFloat.__iadd__,
    RedisFloat.__isub__,
    RedisFloat.__imul__,
    RedisFloat.__itruediv__,
    RedisFloat.__ifloordiv__,
    RedisFloat.__imod__,
    RedisFloat.__ipow__,
    # RedisDatetime
    RedisDatetime.__iadd__,
    RedisDatetime.__isub__,
    # RedisDatetimeTimestamp
    RedisDatetimeTimestamp.__iadd__,
    RedisDatetimeTimestamp.__isub__,
)
ARITHMETIC_SPECIAL_FIELD_METHODS = _group()
ARITHMETIC_MODEL_METHODS = _group()

ARITHMETIC_METHODS = (
    ARITHMETIC_REDIS_TYPE_METHODS
    | ARITHMETIC_SPECIAL_FIELD_METHODS
    | ARITHMETIC_MODEL_METHODS
)


# ── Private helpers: single-underscore internals, not Redis operations ────

PRIVATE_REDIS_TYPE_METHODS = _group(
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
)

PRIVATE_METHODS = (
    PRIVATE_REDIS_TYPE_METHODS | PRIVATE_SPECIAL_FIELD_METHODS | PRIVATE_MODEL_METHODS
)
