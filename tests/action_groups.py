from typing import Callable

import rapyer
from rapyer import find_redis_models, init_rapyer, teardown_rapyer
from rapyer.base import AtomicRedisModel
from rapyer.types import RedisSet
from rapyer.types.base import BaseRedisType, RedisType
from rapyer.types.byte import RedisBytes
from rapyer.types.datetime import RedisDatetime, RedisDatetimeTimestamp
from rapyer.types.dct import RedisDict
from rapyer.types.external import ExternalFieldType
from rapyer.types.foreign_key import ForeignKey
from rapyer.types.generic import GenericRedisType
from rapyer.types.lst import RedisList
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.relational import RelationalFieldType
from rapyer.types.special import SpecialFieldType
from tests.coverage_helpers import cover_tuple


def _group(*methods: Callable) -> frozenset[tuple[str, str]]:
    return frozenset(cover_tuple(m) for m in methods)


# PRIVATE_METHODS — exact (class, method) match; subclass overrides are NOT auto-filtered.
PRIVATE_METHODS = _group(
    # RedisBytes
    RedisBytes._validate_pickle,
    RedisBytes._serialize_pickle,
    # RedisDatetimeTimestamp
    RedisDatetimeTimestamp._validate_timestamp,
    RedisDatetimeTimestamp._serialize_timestamp,
    # RedisPriorityQueue
    RedisPriorityQueue._dump_member,
    RedisPriorityQueue._dump_members,
    RedisPriorityQueue._load_member,
    # Redis set
    RedisSet._dump_members,
    RedisSet._dump_member,
    RedisSet._load_members,
    RedisSet.queue_special_loads_in_pipeline,
    RedisSet._tmp_key,
    # Generic
    GenericRedisType.inner_field_traits,
    # AtomicRedisModel
    AtomicRedisModel._search_keys_by_query,
    AtomicRedisModel.build_redis_model,
    AtomicRedisModel.acreate_index,
    AtomicRedisModel.adelete_index,
    AtomicRedisModel.update,
    AtomicRedisModel.redis_dump_json,
    AtomicRedisModel.redis_dump,
    AtomicRedisModel.is_inner_model,
    AtomicRedisModel.model_post_init,
    AtomicRedisModel.validate_sub_model,
    AtomicRedisModel._all_keys_for_key,
    AtomicRedisModel._iter_expanded_filter_batches,
    AtomicRedisModel._resolve_key,
    # Pure in-memory identity minting (lazily fills _pk); no Redis round trip.
    AtomicRedisModel._ensure_pk,
    # Pure in-memory traversal over special fields; no round trip, so coverage doesn't apply.
    AtomicRedisModel._iter_special_fields,
    AtomicRedisModel._ttl_keys,
    # Pure in-memory FK-field check gating the TTL cascade fast path; no Redis.
    AtomicRedisModel._needs_cascade_script,
    AtomicRedisModel.class_key_initials,
    AtomicRedisModel.index_name,
    AtomicRedisModel.create_expressions,
    AtomicRedisModel.create_redis_model,
    AtomicRedisModel.init_class,
    AtomicRedisModel.iter_filter_batches,
    AtomicRedisModel.should_refresh,
    AtomicRedisModel.should_refresh_for_action,
    AtomicRedisModel.build_redis_dump_exclude,
    AtomicRedisModel.inner_field_traits,
    AtomicRedisModel.fields_with,
    AtomicRedisModel.fields_reaching,
    AtomicRedisModel.queue_special_loads_in_pipeline,
    # Abstract stub, never executed; ForeignKey.afetch is the real READ|FETCH action.
    RelationalFieldType.afetch,
    # Pure in-memory cache drop (self._value = None); no Redis round trip.
    ForeignKey.aunload,
)

# PRIVATE_INHERITED_METHODS — MRO-aware: inheritors and overriders are filtered too, so this is
# the home for internal helpers whose contract is shared across the type hierarchy.
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
    SpecialFieldType.special_field_key,
    SpecialFieldType.asave_special,
    SpecialFieldType.adelete_special,
    SpecialFieldType.aduplicate_special,
    # Lua codegen / ARGV helpers for SF dispatch: they build strings, not Redis round trips.
    # Shared contract across the SF hierarchy — subclasses override several of them.
    SpecialFieldType.lua_type_name,
    SpecialFieldType.lua_save_snippet,
    SpecialFieldType.lua_load_snippet,
    SpecialFieldType.lua_save_payload,
    SpecialFieldType.has_lua_load_output,
    # FieldTrait declarations and the walks that read them: pure class-level
    # introspection over _field_specs, no Redis round trip. Shared contract across the
    # hierarchy, so subclasses override several of them.
    ExternalFieldType.traits,
    ExternalFieldType.inner_field_traits,
    ExternalFieldType.config_type,
    ExternalFieldType.extract_config,
    ExternalFieldType.owns_serialization,
    ExternalFieldType.owned_redis_keys,
    SpecialFieldType.owned_redis_keys,
    SpecialFieldType.cascade_container_kind,
    RedisSet.traits,
    RedisSet.cascade_container_kind,
    RedisPriorityQueue.traits,
    RedisPriorityQueue.cascade_container_kind,
    ForeignKey.traits,
    RelationalFieldType.relational_targets,
    AtomicRedisModel.walk,
    AtomicRedisModel.redis_link_fields,
    RedisPriorityQueue.aremove,
    AtomicRedisModel.redis_schema,
    # Fixed-contract pydantic hook, structurally never an action, so every override is filtered.
    # One entry per branch root: RedisType covers its whole branch via MRO name-matching.
    RedisType.__get_pydantic_core_schema__,
    RedisSet.__get_pydantic_core_schema__,
    RedisPriorityQueue.__get_pydantic_core_schema__,
    ForeignKey.__get_pydantic_core_schema__,
)

# NON_ACTION_METHODS — helpers that aren't Redis actions, so they skip the coverage checks.
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
    AtomicRedisModel.refresh_ttl,
    # afind_keys / aexists return keys or existence only, never model data, so no TTL refresh.
    AtomicRedisModel.afind_keys,
    AtomicRedisModel.aexists,
    rapyer.aexists,
    rapyer.apipeline,  # TODO - this should change once we add update on each action in the ttl
    # Language/pydantic protocol dunders, listed by exact (class, name) so a NEW override surfaces
    # for a decision — unlike __get_pydantic_core_schema__, which can never be an action at all.
    AtomicRedisModel.__eq__,
    AtomicRedisModel.__init_subclass__,
    # __setattr__ does queue pipeline writes; the pipeline field-assignment tests cover that.
    AtomicRedisModel.__setattr__,
    ForeignKey.__init__,
    ForeignKey.__eq__,
    ForeignKey.__hash__,
    ForeignKey.__repr__,
    ForeignKey.__getattr__,
    ForeignKey.__class_getitem__,
    GenericRedisType.__init__,
    RedisDict.__init__,
    RedisList.__init__,
    RedisSet.__init__,
    RedisPriorityQueue.__eq__,
    RedisDatetime.__new__,
)


# Pipeline-only sync actions: outside an open pipeline they don't mutate the local mirror, so they
# can't satisfy the native-Python-effect contract. Subtracted from COVER_SYNC_NATIVE_EFFECT.
SYNC_NATIVE_EFFECT_GROUP = _group(RedisList.remove_range)


# Async ERASE actions that cannot be corrupted because they have no local mirror at all
# (RedisPriorityQueue is a pure Redis proxy). Subtracted from COVER_STALE_MIRROR_IN_PIPELINE.
STALE_MIRROR_GROUP = frozenset(
    {
        ("RedisPriorityQueue", "aclear"),
        ("RedisPriorityQueue", "apop"),
    }
)


# Sync ERASE methods whose native form never raises after local-mirror corruption.
# Subtracted from the COVER_SYNC_NATIVE_RAISES_ON_CORRUPTION expected set.
SYNC_NATIVE_RAISES_GROUP = SYNC_NATIVE_EFFECT_GROUP | _group(
    # Only ``set.remove`` raises KeyError; discard/clear/bulk-update are tolerant by design.
    RedisSet.discard,
    RedisSet.clear,
    RedisSet.difference_update,
    RedisSet.intersection_update,
    RedisList.clear,
    RedisDict.clear,
)


# Read/fetch actions not marked READ, so the ignore_groups=READ exclusion misses them. They return
# a value and cannot be deferred in a pipeline, so they leave COVER_PIPELINE_ATOM too.
ADDITIONAL_READ_ACTIONS = _group(ForeignKey.afetch)
