from typing import Annotated, ClassVar, Optional

from pydantic import Field

from rapyer.base import AtomicRedisModel
from rapyer.cascade import CascadeTTL
from rapyer.config import RedisConfig
from rapyer.types.foreign_key import Reference

# D-08: every cascade fixture below gets this ttl so no `classes[<class>].ttl`
# lookup in the Lua write phase can ever resolve to nil, regardless of which
# fixture 02-04 roots a real cascade-apply invocation at.
CASCADE_FIXTURE_TTL_SECONDS = 3600


class CascadeAuthor(AtomicRedisModel):
    name: str = "anon"

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadeBookDirect(AtomicRedisModel):
    """Shape 1: direct FK field carrying an explicit CascadeTTL."""

    title: str = "untitled"
    author: Annotated[Reference[CascadeAuthor], CascadeTTL(enabled=False)]

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadeBookCollection(AtomicRedisModel):
    """Shape 2: collection-of-FK field carrying the marker on the collection itself."""

    title: str = "untitled"
    co_authors: Annotated[list[Reference[CascadeAuthor]], CascadeTTL()] = Field(
        default_factory=list
    )

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadeProfile(AtomicRedisModel):
    """Nested submodel whose own field carries the cascade marker (shape 3)."""

    mentor: Annotated[Reference[CascadeAuthor], CascadeTTL()]

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadeBookNested(AtomicRedisModel):
    """Shape 3: nested submodel containing its own cascade-enabled FK field."""

    title: str = "untitled"
    profile: CascadeProfile

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadeBookPlain(AtomicRedisModel):
    """No CascadeTTL anywhere — used for the COMPAT-02 'no marker present' case."""

    title: str = "untitled"
    author: Reference[CascadeAuthor]

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


# --- Plan 01-03 additions: CascadePlanner traversal fixtures (shape 1) ---


class CascadeChainNode(AtomicRedisModel):
    """
    Self-referencing chain node. ``next`` carries no per-field marker — cascade
    is driven entirely by this class's own blanket ``Meta.cascade_ttl``, so a
    hop through ``next`` always takes the DECREMENTING blanket path
    (``CascadePlanner._next_hop``'s "established" branch) instead of an
    explicit per-field override, which would REFRESH (never decrement) the
    budget at every hop of a self-referencing field (D-03 revised).
    """

    name: str = "node"
    next: Optional[Reference["CascadeChainNode"]] = None

    Meta: ClassVar[RedisConfig] = RedisConfig(
        cascade_ttl=CascadeTTL(), ttl=CASCADE_FIXTURE_TTL_SECONDS
    )


class CascadeChainRoot(AtomicRedisModel):
    """Enters a CascadeChainNode chain with an explicit per-field depth cap."""

    head: Annotated[Reference[CascadeChainNode], CascadeTTL(depth=2)]

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadeExtendingNode(AtomicRedisModel):
    """A node whose own explicit depth extends past a shallower ancestor's budget."""

    name: str = "extending"
    onward: Annotated[Reference[CascadeChainNode], CascadeTTL(depth=5)]

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadeShallowRoot(AtomicRedisModel):
    """Enters CascadeExtendingNode with a near-exhausted budget (depth=0)."""

    entry: Annotated[Reference[CascadeExtendingNode], CascadeTTL(depth=0)]

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadeDiamondChild(AtomicRedisModel):
    """Plain leaf with no FK — the shared child in a diamond graph."""

    name: str = "child"

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadeDiamondRoot(AtomicRedisModel):
    """Two cascade-enabled fields pointing at the SAME child (dedup test)."""

    left: Annotated[Reference[CascadeDiamondChild], CascadeTTL()]
    right: Annotated[Reference[CascadeDiamondChild], CascadeTTL()]

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadeMultiDepthRoot(AtomicRedisModel):
    """D-11: sibling root fields with independent, non-reconciled depth ceilings."""

    short_reach: Annotated[Reference[CascadeChainNode], CascadeTTL(depth=1)]
    long_reach: Annotated[Reference[CascadeChainNode], CascadeTTL(depth=3)]

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadeBlanketLeaf(AtomicRedisModel):
    """Plain leaf reached purely via a blanket-enabled global default."""

    name: str = "leaf"

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadeBlanketRoot(AtomicRedisModel):
    """D-01/D-07: an unannotated FK field cascades purely via the blanket global."""

    child: Reference[CascadeBlanketLeaf]

    Meta: ClassVar[RedisConfig] = RedisConfig(
        cascade_ttl=CascadeTTL(depth=2), ttl=CASCADE_FIXTURE_TTL_SECONDS
    )


class CascadeBlanketOptOut(AtomicRedisModel):
    """D-01/D-02: a field opts OUT of an otherwise-blanket-enabled global."""

    child: Annotated[Reference[CascadeBlanketLeaf], CascadeTTL(enabled=False)]

    Meta: ClassVar[RedisConfig] = RedisConfig(
        cascade_ttl=CascadeTTL(depth=2), ttl=CASCADE_FIXTURE_TTL_SECONDS
    )


# --- Plan 01-03 Task 2 additions: shapes 2/3 + D-07 full-shape blanket coverage ---


class CascadeBlanketCollectionRoot(AtomicRedisModel):
    """D-07: an unannotated collection-of-FK field cascades via the blanket global."""

    children: list[Reference[CascadeBlanketLeaf]] = Field(default_factory=list)

    Meta: ClassVar[RedisConfig] = RedisConfig(
        cascade_ttl=CascadeTTL(depth=2), ttl=CASCADE_FIXTURE_TTL_SECONDS
    )


class CascadeBlanketNestedProfile(AtomicRedisModel):
    """
    D-07: an unannotated nested-submodel FK field cascades when the NESTED
    class's own ``Meta.cascade_ttl`` is blanket-enabled — the blanket default
    that matters for shape 3 belongs to the nested class, not its holder.
    """

    mentor: Reference[CascadeBlanketLeaf]

    Meta: ClassVar[RedisConfig] = RedisConfig(
        cascade_ttl=CascadeTTL(depth=2), ttl=CASCADE_FIXTURE_TTL_SECONDS
    )


class CascadeBlanketNestedHolder(AtomicRedisModel):
    """Holder for CascadeBlanketNestedProfile — no Meta override needed."""

    profile: CascadeBlanketNestedProfile

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadeNestedDepthRoot(AtomicRedisModel):
    """
    Enters CascadeBlanketNestedHolder with an explicit depth=1, proving the
    zero-hop nested-submodel walk doesn't consume the budget before the real
    FK hop into ``mentor`` (which decrements via the profile's own blanket).
    """

    holder: Annotated[Reference[CascadeBlanketNestedHolder], CascadeTTL(depth=1)]

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)
