from typing import Callable

import rapyer
from rapyer import find_redis_models, init_rapyer, teardown_rapyer
from rapyer.base import AtomicRedisModel
from rapyer.types import RedisSet
from rapyer.types.base import BaseRedisType, RedisType
from rapyer.types.byte import RedisBytes
from rapyer.types.datetime import RedisDatetime, RedisDatetimeTimestamp
from rapyer.types.dct import RedisDict
from rapyer.types.foreign_key import ForeignKey
from rapyer.types.generic import GenericRedisType
from rapyer.types.lst import RedisList
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.relational import RelationalFieldType
from rapyer.types.special import SpecialFieldType
from tests.coverage_helpers import cover_tuple


def _group(*methods: Callable) -> frozenset[tuple[str, str]]:
    return frozenset(cover_tuple(m) for m in methods)


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
    GenericRedisType.contains_sf_field,
    GenericRedisType.contains_fk_field,
    RedisSet.contains_fk_field,
    RedisPriorityQueue.contains_fk_field,
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
    # Pure in-memory traversal / key enumeration for special fields — no
    # Redis round trips, so pipeline/TTL coverage doesn't apply.
    AtomicRedisModel._iter_special_fields,
    # Private prepare-pass orchestrator; the RedisText calls it feeds are what the matrix covers.
    AtomicRedisModel._aprepare_special_fields,
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
    AtomicRedisModel.contains_sf_field,
    AtomicRedisModel.contains_fk_field,
    AtomicRedisModel.queue_special_loads_in_pipeline,
    # Abstract relational stub — never executed; the concrete ForeignKey.afetch
    # override is the real READ|FETCH action and is covered as one.
    RelationalFieldType.afetch,
    # Pure in-memory cache drop (sets self._value = None); no Redis round trip,
    # so the pipeline/TTL/effect action matrix doesn't apply.
    ForeignKey.aunload,
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
    SpecialFieldType.special_field_key,
    SpecialFieldType.asave_special,
    SpecialFieldType.adelete_special,
    SpecialFieldType.aduplicate_special,
    # Pre-pipeline batch materialization seam (D-07/D-08) - joins the other SF-lifecycle methods above.
    SpecialFieldType.aprepare_many,
    # Lua codegen / payload helpers for aget_or_create's server-side SF
    # dispatch: they build script source and ARGV strings, not Redis round
    # trips, so they aren't actions subject to pipeline/TTL coverage. Shared
    # contract across the SF hierarchy (subclasses override several of them).
    SpecialFieldType.lua_type_name,
    SpecialFieldType.lua_save_snippet,
    SpecialFieldType.lua_load_snippet,
    SpecialFieldType.lua_save_payload,
    SpecialFieldType.has_lua_load_output,
    RedisPriorityQueue.aremove,
    AtomicRedisModel.redis_schema,
    # Pydantic schema hook — a fixed-contract pydantic method (build a core
    # schema at class-definition time); structurally never a Redis action, so
    # every override across the hierarchy is filtered. One entry per branch
    # root: RedisType covers its whole branch (GenericRedisType, RedisBytes,
    # RedisDatetimeTimestamp, ...) via MRO name-matching.
    RedisType.__get_pydantic_core_schema__,
    RedisSet.__get_pydantic_core_schema__,
    RedisPriorityQueue.__get_pydantic_core_schema__,
    ForeignKey.__get_pydantic_core_schema__,
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
    AtomicRedisModel.refresh_ttl,
    # afind_keys / aexists are lightweight queries (keys / existence only) that
    # never load model data, so TTL refresh doesn't apply.
    AtomicRedisModel.afind_keys,
    AtomicRedisModel.aexists,
    rapyer.aexists,
    rapyer.apipeline,  # TODO - this should change once we add update on each action in the ttl
    # ── Python protocol dunders ───────────────────────────────────────────
    # Construction, equality, hashing, repr, attribute access, generic
    # parameterization, and class-build hooks. Language/pydantic protocol
    # methods, not Redis actions. Listed by exact (class, name) so a NEW
    # subclass that overrides one surfaces for a conscious decision rather than
    # being silently skipped (unlike __get_pydantic_core_schema__, whose
    # contract can never be an action — see PRIVATE_INHERITED_METHODS).
    AtomicRedisModel.__eq__,
    AtomicRedisModel.__init_subclass__,
    # __setattr__ DOES queue pipeline writes on field assignment, but that
    # behavior is covered by the dedicated pipeline field-assignment tests,
    # not the per-method action matrix.
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


# SYNC_NATIVE_EFFECT_GROUP — sync action methods that are pipeline-only by
# design: outside an open pipeline they do not mutate the local mirror, so
# they cannot satisfy the "same effect as native Python" contract checked by
# COVER_SYNC_NATIVE_EFFECT. Subtracted from that coverage check's expected set.
SYNC_NATIVE_EFFECT_GROUP = _group(RedisList.remove_range)


# STALE_MIRROR_GROUP — async ERASE actions that cannot be corrupted because
# they have no local mirror. RedisPriorityQueue is a pure Redis proxy with no
# inherited Python container, so there is nothing to mutate locally.
# Subtracted from the COVER_STALE_MIRROR_IN_PIPELINE expected set.
STALE_MIRROR_GROUP = frozenset(
    {
        ("RedisPriorityQueue", "aclear"),
        ("RedisPriorityQueue", "apop"),
    }
)


# SYNC_NATIVE_RAISES_GROUP — sync ERASE methods whose native equivalent never
# raises after local-mirror corruption (only ``set.remove`` raises KeyError;
# discard, clear, and the bulk-update variants are tolerant by design).
# Subtracted from the COVER_SYNC_NATIVE_RAISES_ON_CORRUPTION expected set.
SYNC_NATIVE_RAISES_GROUP = SYNC_NATIVE_EFFECT_GROUP | _group(
    RedisSet.discard,
    RedisSet.clear,
    RedisSet.difference_update,
    RedisSet.intersection_update,
    RedisList.clear,
    RedisDict.clear,
)


# ADDITIONAL_READ_ACTIONS — read/fetch actions that are not marked with the
# READ action group, so the group-based ``ignore_groups=READ`` exclusion misses
# them. They resolve and return a value and cannot be deferred inside a pipeline,
# so pipeline-atomicity does not apply. Excluded from COVER_PIPELINE_ATOM
# alongside the marked READ actions.
ADDITIONAL_READ_ACTIONS = _group(ForeignKey.afetch)
