from typing import Annotated, ClassVar, Optional

from pydantic import Field

from rapyer.base import AtomicRedisModel
from rapyer.cascade import CascadeTTL
from rapyer.config import RedisConfig
from rapyer.fields.key import Key
from rapyer.types.foreign_key import Reference
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.redis_set import RedisSet

# Every cascade fixture below gets this ttl so no `classes[<class>].ttl`
# lookup in the Lua write phase can ever resolve to nil, regardless of which
# fixture roots a real cascade-apply invocation at.
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


class CascadeDictCollectionRoot(AtomicRedisModel):
    """Shape 2 variant: dict[K, Reference] carries the marker on the collection itself."""

    title: str = "untitled"
    co_authors: Annotated[dict[str, Reference[CascadeAuthor]], CascadeTTL()] = Field(
        default_factory=dict
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
    """No CascadeTTL anywhere — used for the 'no marker present' case."""

    title: str = "untitled"
    author: Reference[CascadeAuthor]

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


# --- Cascade-edge-classification fixtures (shape 1) ---


class CascadeChainNode(AtomicRedisModel):
    """
    Self-referencing chain node. ``next`` carries no per-field marker — cascade
    is driven entirely by this class's own blanket ``Meta.cascade_ttl``, so a
    hop through ``next`` always takes the DECREMENTING blanket path
    (the Lua apply script's ``next_hop`` "established" branch) instead of an
    explicit per-field override, which would REFRESH (never decrement) the
    budget at every hop of a self-referencing field.
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
    """Sibling root fields with independent, non-reconciled depth ceilings."""

    short_reach: Annotated[Reference[CascadeChainNode], CascadeTTL(depth=1)]
    long_reach: Annotated[Reference[CascadeChainNode], CascadeTTL(depth=3)]

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadeBlanketLeaf(AtomicRedisModel):
    """Plain leaf reached purely via a blanket-enabled global default; also
    carries an onward blanket edge so a node reached at budget=0 (via
    another class's blanket decrement) proves depth-budget truncation."""

    name: str = "leaf"
    onward: Optional[Reference["CascadeBlanketLeaf"]] = None

    Meta: ClassVar[RedisConfig] = RedisConfig(
        cascade_ttl=CascadeTTL(), ttl=CASCADE_FIXTURE_TTL_SECONDS
    )


class CascadeBlanketRoot(AtomicRedisModel):
    """An unannotated FK field cascades purely via the blanket global."""

    child: Reference[CascadeBlanketLeaf]

    Meta: ClassVar[RedisConfig] = RedisConfig(
        cascade_ttl=CascadeTTL(depth=2), ttl=CASCADE_FIXTURE_TTL_SECONDS
    )


class CascadeBlanketOptOut(AtomicRedisModel):
    """A field opts OUT of an otherwise-blanket-enabled global."""

    child: Annotated[Reference[CascadeBlanketLeaf], CascadeTTL(enabled=False)]

    Meta: ClassVar[RedisConfig] = RedisConfig(
        cascade_ttl=CascadeTTL(depth=2), ttl=CASCADE_FIXTURE_TTL_SECONDS
    )


# --- Shapes 2/3 + full-shape blanket coverage ---


class CascadeBlanketCollectionRoot(AtomicRedisModel):
    """An unannotated collection-of-FK field cascades via the blanket global."""

    children: list[Reference[CascadeBlanketLeaf]] = Field(default_factory=list)

    Meta: ClassVar[RedisConfig] = RedisConfig(
        cascade_ttl=CascadeTTL(depth=2), ttl=CASCADE_FIXTURE_TTL_SECONDS
    )


class CascadeBlanketNestedProfile(AtomicRedisModel):
    """
    An unannotated nested-submodel FK field cascades when the NESTED
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


# --- Special-field-child gap closure + shared-child fixtures ---


class CascadeSpecialChild(AtomicRedisModel):
    """
    Cascade-reachable child carrying its OWN special fields (RedisSet /
    RedisPriorityQueue) — closes the test gap:
    cascade_ttl_apply must refresh a reached child's special-field keys too,
    not just its main key.

    ``name`` is a plain field (not just special fields) so the model's own
    JSON dump is never the empty object ``{}`` — fakeredis's ``EXISTS``/``TTL``
    do not recognize a RedisJSON key whose root document is an empty dict as
    present (a documented fakeredis/real-Redis divergence; see CONCERNS.md).
    """

    name: str = "special_child"
    tags: RedisSet[str] = Field(default_factory=RedisSet)
    scores: RedisPriorityQueue[float] = Field(default_factory=RedisPriorityQueue)

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadeSpecialParent(AtomicRedisModel):
    """Cascade root pointing at CascadeSpecialChild (shape 1 + special-field child)."""

    child: Annotated[Reference[CascadeSpecialChild], CascadeTTL()]

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadeWR02Grandchild(AtomicRedisModel):
    """Plain leaf, reachable only through CascadeWR02SharedChild's own edge."""

    name: str = "grandchild"

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadeWR02SharedChild(AtomicRedisModel):
    """Shared child reached via two sibling root edges with differing depth budgets."""

    next: Annotated[Reference[CascadeWR02Grandchild], CascadeTTL()]

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadeWR02Root(AtomicRedisModel):
    """
    Two fields point at the SAME saved CascadeWR02SharedChild instance
    but carry different depth budgets (the diamond-with-differing-depths
    scenario). The shared child's OWN key is always refreshed
    regardless of DFS visit order (first-visit dedup); only its deeper
    descendant's (the grandchild's) reach is order-dependent and therefore
    deliberately not asserted one way or the other.
    """

    deep_path: Annotated[Reference[CascadeWR02SharedChild], CascadeTTL(depth=5)]
    shallow_path: Annotated[Reference[CascadeWR02SharedChild], CascadeTTL(depth=1)]

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadeMaxBudgetRoot(AtomicRedisModel):
    """
    Max-budget-wins regression: two fields point at the SAME saved
    ``CascadeChainNode`` head with differing finite depth budgets. Unlike
    ``CascadeWR02SharedChild.next`` (an explicit per-field override edge that
    always refreshes regardless of the inherited budget), ``CascadeChainNode.next``
    is a BLANKET (non-override) edge driven by the class's own global
    ``Meta.cascade_ttl`` — it genuinely decrements a real remaining budget on
    every established hop. That makes the two differing budgets here (4 vs 1)
    actually distinguishable: the shared head's onward reach depends on which
    budget it is walked at, rather than being silently masked
    by override semantics.
    """

    deep_path: Annotated[Reference[CascadeChainNode], CascadeTTL(depth=4)]
    shallow_path: Annotated[Reference[CascadeChainNode], CascadeTTL(depth=1)]

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


# --- SF-held-ref fixtures (FK elements held inside RedisSet / RedisPriorityQueue) ---


class CascadeSetRefParent(AtomicRedisModel):
    """SF-held-ref shape: FK references held inside a RedisSet, per-field enabled."""

    name: str = "set_ref"
    refs: Annotated[RedisSet[Reference[CascadeAuthor]], CascadeTTL()] = Field(
        default_factory=RedisSet
    )

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadePQRefParent(AtomicRedisModel):
    """SF-held-ref shape: FK references held inside a RedisPriorityQueue."""

    name: str = "pq_ref"
    queue: Annotated[
        RedisPriorityQueue[Reference[CascadeAuthor]], CascadeTTL(depth=2)
    ] = Field(default_factory=RedisPriorityQueue)

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadeSetRefBlanket(AtomicRedisModel):
    """SF-held-ref field with no per-field marker; cascades via the blanket global."""

    name: str = "set_ref_blanket"
    refs: RedisSet[Reference[CascadeAuthor]] = Field(default_factory=RedisSet)

    Meta: ClassVar[RedisConfig] = RedisConfig(
        cascade_ttl=CascadeTTL(depth=2), ttl=CASCADE_FIXTURE_TTL_SECONDS
    )


class CascadeSetRefOptOut(AtomicRedisModel):
    """SF-held-ref field opts OUT of an otherwise-blanket-enabled global."""

    name: str = "set_ref_opt_out"
    refs: Annotated[RedisSet[Reference[CascadeAuthor]], CascadeTTL(enabled=False)] = (
        Field(default_factory=RedisSet)
    )

    Meta: ClassVar[RedisConfig] = RedisConfig(
        cascade_ttl=CascadeTTL(), ttl=CASCADE_FIXTURE_TTL_SECONDS
    )


class CascadeSetRefNoTtlTarget(AtomicRedisModel):
    """SF-held-ref target with no Meta.ttl — fail-fast fixture, not registered."""

    name: str = "no_ttl_target"

    # Excluded from REDIS_MODELS so it never trips init_rapyer()'s full-set validation.
    Meta: ClassVar[RedisConfig] = RedisConfig(init_with_rapyer=False)


class CascadeSetRefToNoTtl(AtomicRedisModel):
    """Root has a ttl; its SF-held-ref target does not — target violation."""

    name: str = "set_ref_to_no_ttl"
    refs: Annotated[RedisSet[Reference[CascadeSetRefNoTtlTarget]], CascadeTTL()] = (
        Field(default_factory=RedisSet)
    )

    Meta: ClassVar[RedisConfig] = RedisConfig(
        ttl=CASCADE_FIXTURE_TTL_SECONDS, init_with_rapyer=False
    )


class CascadeSetRefRootNoTtl(AtomicRedisModel):
    """Root-with-only-SF-edges has no Meta.ttl — root violation."""

    name: str = "set_ref_root_no_ttl"
    refs: Annotated[RedisSet[Reference[CascadeAuthor]], CascadeTTL()] = Field(
        default_factory=RedisSet
    )

    Meta: ClassVar[RedisConfig] = RedisConfig(init_with_rapyer=False)


# --- SF-held-ref hard-shape fixtures (Phase 2: server-side traversal proof) ---


class CascadeSetRefSelfNode(AtomicRedisModel):
    """Self-reference held inside a RedisSet: the node's own key can be a
    member of its own ``peers`` field. Proves the shared visited map
    terminates this cycle via the SMEMBERS read branch instead of hanging."""

    name: str = "set_ref_self"
    peers: Annotated[RedisSet[Reference["CascadeSetRefSelfNode"]], CascadeTTL()] = (
        Field(default_factory=RedisSet)
    )

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadePQRefSelfNode(AtomicRedisModel):
    """Same self-reference shape as CascadeSetRefSelfNode but held inside a
    RedisPriorityQueue instead of a RedisSet — proves the cycle-safety
    guarantee holds independently for the ZRANGE read branch."""

    name: str = "pq_ref_self"
    peers: Annotated[
        RedisPriorityQueue[Reference["CascadePQRefSelfNode"]], CascadeTTL()
    ] = Field(default_factory=RedisPriorityQueue)

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadeMixedEdgeSharedChild(AtomicRedisModel):
    """Chain node reached by CascadeMixedEdgeSharedChildRoot via both an
    inline edge and an SF-held-ref edge. Blanket (non-override) cascade so
    depth genuinely decrements on every established hop."""

    name: str = "mixed_edge_shared_child"
    onward: Optional[Reference["CascadeMixedEdgeSharedChild"]] = None

    Meta: ClassVar[RedisConfig] = RedisConfig(
        cascade_ttl=CascadeTTL(), ttl=CASCADE_FIXTURE_TTL_SECONDS
    )


class CascadeMixedEdgeSharedChildRoot(AtomicRedisModel):
    """Two fields point at the SAME saved CascadeMixedEdgeSharedChild
    instance: ``shallow_inline`` (inline FK, override, depth=1) and
    ``deep_set`` (SF-held-ref, override, depth=4). Proves SF edges
    participate in the SAME best-budget-per-node visited map as inline
    edges — the shared child is walked at the larger SF budget regardless
    of which edge's push_child call happens first."""

    name: str = "mixed_edge_shared_child_root"
    shallow_inline: Annotated[
        Reference[CascadeMixedEdgeSharedChild], CascadeTTL(depth=1)
    ]
    deep_set: Annotated[
        RedisSet[Reference[CascadeMixedEdgeSharedChild]], CascadeTTL(depth=4)
    ] = Field(default_factory=RedisSet)

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadeSfDiamondChild(AtomicRedisModel):
    """Plain leaf reached by CascadeSfDiamondRoot via two different
    SF-container kinds on the same root (SET and ZSET)."""

    name: str = "sf_diamond_child"

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadeSfDiamondRoot(AtomicRedisModel):
    """Two independent SF-held-ref fields (one RedisSet, one
    RedisPriorityQueue) both pointing at the SAME saved
    CascadeSfDiamondChild instance. Proves a child reached via two
    different SF-container kinds converges through the shared visited map
    and is re-armed exactly once, with no double-processing error."""

    name: str = "sf_diamond_root"
    left: Annotated[RedisSet[Reference[CascadeSfDiamondChild]], CascadeTTL()] = Field(
        default_factory=RedisSet
    )
    right: Annotated[
        RedisPriorityQueue[Reference[CascadeSfDiamondChild]], CascadeTTL()
    ] = Field(default_factory=RedisPriorityQueue)

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


# --- Multi-candidate FK fixtures (union targets) ---


class CascadeUnionMemberA(AtomicRedisModel):
    """Concrete union member A — a plain ttl-bearing leaf."""

    name: str = "union_member_a"

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadeUnionMemberB(AtomicRedisModel):
    """Concrete union member B — a plain ttl-bearing leaf."""

    name: str = "union_member_b"

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadeUnionOwner(AtomicRedisModel):
    """Owns a scalar FK whose target is a union of two models."""

    ref: Annotated[Reference[CascadeUnionMemberA | CascadeUnionMemberB], CascadeTTL()]

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


# --- Multi-candidate FK fixtures (polymorphic base + registered subclasses) ---


class CascadePolyBase(AtomicRedisModel):
    """Registered polymorphic base — a candidate in its own right."""

    name: str = "poly_base"

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadePolySub1(CascadePolyBase):
    """First registered subclass of CascadePolyBase."""

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadePolySub2(CascadePolyBase):
    """Second registered subclass of CascadePolyBase."""

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadePolyOwner(AtomicRedisModel):
    """Owns a scalar FK to a polymorphic base with registered subclasses."""

    ref: Annotated[Reference[CascadePolyBase], CascadeTTL()]

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadePolyDedupOwner(AtomicRedisModel):
    """Union whose members overlap: a subclass listed beside its own base."""

    ref: Annotated[Reference[CascadePolyBase | CascadePolySub1], CascadeTTL()]

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


# --- The same union target across every remaining FK shape ---


class CascadeUnionListOwner(AtomicRedisModel):
    """Collection-of-union shape: list[Reference[A | B]], marker on the collection."""

    refs: Annotated[
        list[Reference[CascadeUnionMemberA | CascadeUnionMemberB]], CascadeTTL()
    ] = Field(default_factory=list)

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadeUnionDictOwner(AtomicRedisModel):
    """Collection-of-union shape: dict[str, Reference[A | B]], marker on the collection."""

    refs: Annotated[
        dict[str, Reference[CascadeUnionMemberA | CascadeUnionMemberB]], CascadeTTL()
    ] = Field(default_factory=dict)

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadeUnionSetOwner(AtomicRedisModel):
    """SF-held-union shape: RedisSet[Reference[A | B]], marker on the special field."""

    refs: Annotated[
        RedisSet[Reference[CascadeUnionMemberA | CascadeUnionMemberB]], CascadeTTL()
    ] = Field(default_factory=RedisSet)

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadeUnionPQOwner(AtomicRedisModel):
    """SF-held-union shape: RedisPriorityQueue[Reference[A | B]], marker on the field."""

    queue: Annotated[
        RedisPriorityQueue[Reference[CascadeUnionMemberA | CascadeUnionMemberB]],
        CascadeTTL(),
    ] = Field(default_factory=RedisPriorityQueue)

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


# --- Mixed-class diamond: two candidate classes share a single leaf ---


class CascadeMultiClassDiamondLeaf(AtomicRedisModel):
    """Plain ttl-bearing leaf FK'd by both diamond members."""

    name: str = "multi_class_diamond_leaf"

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadeMultiClassDiamondMemberA(AtomicRedisModel):
    """Diamond member A — carries a scalar FK to the shared leaf."""

    leaf: Annotated[Reference[CascadeMultiClassDiamondLeaf], CascadeTTL()]

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadeMultiClassDiamondMemberB(AtomicRedisModel):
    """Diamond member B — a different class than A, FK'd to the same shared leaf."""

    leaf: Annotated[Reference[CascadeMultiClassDiamondLeaf], CascadeTTL()]

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadeMultiClassDiamondRoot(AtomicRedisModel):
    """Union-FK root whose two candidate members both lead to one shared leaf."""

    member: Annotated[
        Reference[CascadeMultiClassDiamondMemberA | CascadeMultiClassDiamondMemberB],
        CascadeTTL(),
    ]

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


# --- Colon-bearing Key[...] pk union member (Pitfall 2 lock) ---


class CascadeColonPkMember(AtomicRedisModel):
    """Union member whose Key[str] pk can itself contain a colon."""

    member_id: Key[str]
    name: str = "colon_pk_member"

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


class CascadeColonPkOwner(AtomicRedisModel):
    """Owns a scalar union FK whose candidates include the colon-pk member."""

    ref: Annotated[Reference[CascadeColonPkMember | CascadeUnionMemberA], CascadeTTL()]

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


# --- Union-edge depth-budget fixture ---


class CascadeUnionDepthRoot(AtomicRedisModel):
    """Enters a chain through a union edge under a per-subtree depth cap."""

    # Resolving to CascadeChainNode carries the reset depth=1 budget into its subtree.
    entry: Annotated[
        Reference[CascadeChainNode | CascadeUnionMemberB], CascadeTTL(depth=1)
    ]

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)


# Full cascade-model set shared by unit and integration cascade fixtures.
ALL_CASCADE_MODELS = [
    CascadeAuthor,
    CascadeBookDirect,
    CascadeBookCollection,
    CascadeDictCollectionRoot,
    CascadeProfile,
    CascadeBookNested,
    CascadeBookPlain,
    CascadeChainNode,
    CascadeChainRoot,
    CascadeExtendingNode,
    CascadeShallowRoot,
    CascadeDiamondChild,
    CascadeDiamondRoot,
    CascadeMultiDepthRoot,
    CascadeBlanketLeaf,
    CascadeBlanketRoot,
    CascadeBlanketOptOut,
    CascadeBlanketCollectionRoot,
    CascadeBlanketNestedProfile,
    CascadeBlanketNestedHolder,
    CascadeNestedDepthRoot,
    CascadeSpecialChild,
    CascadeSpecialParent,
    CascadeWR02Grandchild,
    CascadeWR02SharedChild,
    CascadeWR02Root,
    CascadeMaxBudgetRoot,
    CascadeSetRefParent,
    CascadePQRefParent,
    CascadeSetRefBlanket,
    CascadeSetRefOptOut,
    CascadeSetRefSelfNode,
    CascadePQRefSelfNode,
    CascadeMixedEdgeSharedChild,
    CascadeMixedEdgeSharedChildRoot,
    CascadeSfDiamondChild,
    CascadeSfDiamondRoot,
    CascadeUnionMemberA,
    CascadeUnionMemberB,
    CascadeUnionOwner,
    CascadeUnionListOwner,
    CascadeUnionDictOwner,
    CascadeUnionSetOwner,
    CascadeUnionPQOwner,
    CascadeMultiClassDiamondLeaf,
    CascadeMultiClassDiamondMemberA,
    CascadeMultiClassDiamondMemberB,
    CascadeMultiClassDiamondRoot,
    CascadeColonPkMember,
    CascadeColonPkOwner,
    CascadeUnionDepthRoot,
]
