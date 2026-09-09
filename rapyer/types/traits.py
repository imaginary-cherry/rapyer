"""What field types declare about themselves, and what walks require of them."""

from enum import Flag, auto


class FieldTrait(Flag):
    """What a field type contributes to a walk."""

    # INDEXED is deliberately absent — add it only once a walk needs it.

    # Owns a Redis key that dies with the parent; the delete and TTL sweeps collect it.
    # RedisSet: _all_keys_for_key adds __rapyer_special__:{key}:tags to the doc key.
    OWNS_KEYS = auto()
    # Never serialized into the parent JSON, so the document dump excludes the field.
    # RedisSet: build_redis_dump_exclude drops "tags" before JSON.SET writes the doc.
    EXCLUDED_FROM_DOC = auto()
    # Contributes a slot to the load pipeline; lazily-fetched types declare none.
    # RedisSet has it, RedisPriorityQueue does not — apeek/aitems fetch on demand.
    LOADS_WITH_DOC = auto()
    # The live instance must be visited to save it, not just its class-level facts.
    # asave walks _iter_special_fields and calls asave_special() on each RedisSet.
    HOLDS_LIVE_STATE = auto()
    # Names a separate document with its own key and TTL; cascade decides the hop.
    # ForeignKey only: the planner's FK-edge walk turns each into a CascadeEdge.
    REFERENCES_ROOT = auto()
