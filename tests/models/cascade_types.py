from typing import Annotated, ClassVar, Optional

from pydantic import Field

from rapyer.base import AtomicRedisModel
from rapyer.cascade import CascadeTTL
from rapyer.config import RedisConfig
from rapyer.types.foreign_key import Reference


class CascadeAuthor(AtomicRedisModel):
    name: str = "anon"


class CascadeBookDirect(AtomicRedisModel):
    """Shape 1: direct FK field carrying an explicit CascadeTTL."""

    title: str = "untitled"
    author: Annotated[Reference[CascadeAuthor], CascadeTTL(enabled=False)]


class CascadeBookCollection(AtomicRedisModel):
    """Shape 2: collection-of-FK field carrying the marker on the collection itself."""

    title: str = "untitled"
    co_authors: Annotated[list[Reference[CascadeAuthor]], CascadeTTL()] = Field(
        default_factory=list
    )


class CascadeProfile(AtomicRedisModel):
    """Nested submodel whose own field carries the cascade marker (shape 3)."""

    mentor: Annotated[Reference[CascadeAuthor], CascadeTTL()]


class CascadeBookNested(AtomicRedisModel):
    """Shape 3: nested submodel containing its own cascade-enabled FK field."""

    title: str = "untitled"
    profile: CascadeProfile


class CascadeBookPlain(AtomicRedisModel):
    """No CascadeTTL anywhere — used for the COMPAT-02 'no marker present' case."""

    title: str = "untitled"
    author: Reference[CascadeAuthor]


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

    Meta: ClassVar[RedisConfig] = RedisConfig(cascade_ttl=CascadeTTL())


class CascadeChainRoot(AtomicRedisModel):
    """Enters a CascadeChainNode chain with an explicit per-field depth cap."""

    head: Annotated[Reference[CascadeChainNode], CascadeTTL(depth=2)]


class CascadeExtendingNode(AtomicRedisModel):
    """A node whose own explicit depth extends past a shallower ancestor's budget."""

    name: str = "extending"
    onward: Annotated[Reference[CascadeChainNode], CascadeTTL(depth=5)]


class CascadeShallowRoot(AtomicRedisModel):
    """Enters CascadeExtendingNode with a near-exhausted budget (depth=0)."""

    entry: Annotated[Reference[CascadeExtendingNode], CascadeTTL(depth=0)]


class CascadeDiamondChild(AtomicRedisModel):
    """Plain leaf with no FK — the shared child in a diamond graph."""

    name: str = "child"


class CascadeDiamondRoot(AtomicRedisModel):
    """Two cascade-enabled fields pointing at the SAME child (dedup test)."""

    left: Annotated[Reference[CascadeDiamondChild], CascadeTTL()]
    right: Annotated[Reference[CascadeDiamondChild], CascadeTTL()]


class CascadeMultiDepthRoot(AtomicRedisModel):
    """D-11: sibling root fields with independent, non-reconciled depth ceilings."""

    short_reach: Annotated[Reference[CascadeChainNode], CascadeTTL(depth=1)]
    long_reach: Annotated[Reference[CascadeChainNode], CascadeTTL(depth=3)]


class CascadeBlanketLeaf(AtomicRedisModel):
    """Plain leaf reached purely via a blanket-enabled global default."""

    name: str = "leaf"


class CascadeBlanketRoot(AtomicRedisModel):
    """D-01/D-07: an unannotated FK field cascades purely via the blanket global."""

    child: Reference[CascadeBlanketLeaf]

    Meta: ClassVar[RedisConfig] = RedisConfig(cascade_ttl=CascadeTTL(depth=2))


class CascadeBlanketOptOut(AtomicRedisModel):
    """D-01/D-02: a field opts OUT of an otherwise-blanket-enabled global."""

    child: Annotated[Reference[CascadeBlanketLeaf], CascadeTTL(enabled=False)]

    Meta: ClassVar[RedisConfig] = RedisConfig(cascade_ttl=CascadeTTL(depth=2))
