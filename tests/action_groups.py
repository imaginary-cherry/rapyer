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
from tests.integration.pipeline.pipeline_atomicity_base import _cover_tuple


def _group(*methods: Callable) -> frozenset[tuple[str, str]]:
    return frozenset(_cover_tuple(m) for m in methods)


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
    AtomicRedisModel.update,
    AtomicRedisModel.redis_dump_json,
    AtomicRedisModel.redis_dump,
    AtomicRedisModel.is_inner_model,
    AtomicRedisModel.assign_fields_links,
    AtomicRedisModel.validate_sub_model,
    AtomicRedisModel._all_keys_for_key,
    AtomicRedisModel._iter_expanded_filter_batches,
    AtomicRedisModel._resolve_key,
    AtomicRedisModel.class_key_initials,
    AtomicRedisModel.index_name,
    AtomicRedisModel.create_expressions,
    AtomicRedisModel.create_redis_model,
    AtomicRedisModel.init_class,
    AtomicRedisModel.iter_filter_batches,
    AtomicRedisModel.should_refresh,
    AtomicRedisModel.should_refresh_for_action,
)

# PRIVATE_INHERITED_METHODS — MRO-aware. Any subclass that inherits OR
# overrides one of these methods is also filtered. Use this for internal
# helpers whose contract is shared across the type hierarchy
PRIVATE_INHERITED_METHODS = _group(
    BaseRedisType.sub_field_path,
    RedisType.redis_schema,
    RedisType.clone,
    RedisType.serialize_unknown,
    RedisType.deserialize_unknown,
    GenericRedisType.iterate_items,
    GenericRedisType.full_serializer,
    GenericRedisType.full_deserializer,
    GenericRedisType.build_typed_original,
    GenericRedisType.find_inner_type,
    GenericRedisType.schema_for_unknown,
    GenericRedisType.try_deserialize_item,
    RedisDict.validate_dict,
    RedisList.create_new_value,
    RedisList.create_new_values,
    SpecialFieldType.clone,
    SpecialFieldType.asave_special,
    SpecialFieldType.adelete_special,
    SpecialFieldType.aduplicate_special,
    RedisPriorityQueue.find_inner_type,
    RedisPriorityQueue.aremove,
    AtomicRedisModel.redis_schema,
)

# NON_ACTION_METHODS — module-level helpers that aren't Redis actions and
# therefore don't participate in coverage checks.
NON_ACTION_METHODS = _group(
    init_rapyer,
    teardown_rapyer,
    find_redis_models,
    # Distributed lock context manager, not a pipeline-participating write.
    rapyer.alock_from_key,
    AtomicRedisModel.alock_from_key,
    AtomicRedisModel.alock,
    # TTL primitives: they ARE the TTL mechanism, not actions subject to it.
    AtomicRedisModel.aset_ttl,
    AtomicRedisModel.refresh_ttl_if_needed,
    # afind_keys / aexists are lightweight queries (keys / existence only) that
    # never load model data, so TTL refresh doesn't apply.
    AtomicRedisModel.afind_keys,
    AtomicRedisModel.aexists,
    rapyer.aexists,
    rapyer.apipeline,  # TODO - this should change once we add update on each action in the ttl
)
