import os
from datetime import datetime
from typing import Annotated, ClassVar, Dict, List, Optional

from pydantic import Field

from rapyer.actions import ActionGroup
from rapyer.base import AtomicRedisModel
from rapyer.cascade import CascadeTTL
from rapyer.config import RedisConfig
from rapyer.types import RedisDatetimeTimestamp
from rapyer.types.foreign_key import Reference
from tests.models.collection_types import SimpleListModel, StrDictModel
from tests.models.index_types import IndexTestModel
from tests.models.redis_types import DirectRedisIntModel
from tests.models.simple_types import FloatModel, IntModel, StrModel
from tests.models.special_types import GenericRedisSetModel, PriorityQueueModel

BENCHMARK_TTL_SECONDS = 3600


class BenchmarkPipelineModel(AtomicRedisModel):
    """
    Scalar/list/dict-only model for pipeline benchmarks.

    Deliberately omits special fields (RedisPriorityQueue, RedisSet) so the
    benchmark exercises the inline-JSON pipeline path without dragging in the
    per-call SF prefetch from ``apipeline()``.
    """

    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, str] = Field(default_factory=dict)
    name: str = ""
    counter: int = 0
    amount: float = 0.0
    data: bytes = b""
    event_time: datetime = Field(default_factory=datetime.now)
    event_timestamp: RedisDatetimeTimestamp = Field(default_factory=datetime.now)


class BenchmarkPipelineModelWithTTL(BenchmarkPipelineModel):
    Meta: ClassVar[RedisConfig] = RedisConfig(
        ttl=BENCHMARK_TTL_SECONDS,
        refresh_ttl=ActionGroup.all(for_ttl=True),
    )


class StrDictModelWithTTL(StrDictModel):
    Meta: ClassVar[RedisConfig] = RedisConfig(
        ttl=BENCHMARK_TTL_SECONDS,
        refresh_ttl=ActionGroup.all(for_ttl=True),
    )


class SimpleListModelWithTTL(SimpleListModel):
    Meta: ClassVar[RedisConfig] = RedisConfig(
        ttl=BENCHMARK_TTL_SECONDS,
        refresh_ttl=ActionGroup.all(for_ttl=True),
    )


class StrModelWithTTL(StrModel):
    Meta: ClassVar[RedisConfig] = RedisConfig(
        ttl=BENCHMARK_TTL_SECONDS,
        refresh_ttl=ActionGroup.all(for_ttl=True),
    )


class IntModelWithTTL(IntModel):
    Meta: ClassVar[RedisConfig] = RedisConfig(
        ttl=BENCHMARK_TTL_SECONDS,
        refresh_ttl=ActionGroup.all(for_ttl=True),
    )


class FloatModelNoTTL(FloatModel):
    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=None)


class IndexTestModelWithTTL(IndexTestModel):
    Meta: ClassVar[RedisConfig] = RedisConfig(
        ttl=BENCHMARK_TTL_SECONDS,
        refresh_ttl=ActionGroup.all(for_ttl=True),
    )


class DirectRedisIntModelWithTTL(DirectRedisIntModel):
    Meta: ClassVar[RedisConfig] = RedisConfig(
        ttl=BENCHMARK_TTL_SECONDS,
        refresh_ttl=ActionGroup.all(for_ttl=True),
    )


class PriorityQueueModelNoTTL(PriorityQueueModel):
    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=None)


class GenericRedisSetModelNoTTL(GenericRedisSetModel[str]):
    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=None)


class GenericRedisSetModelWithTTL(GenericRedisSetModel[str]):
    Meta: ClassVar[RedisConfig] = RedisConfig(
        ttl=BENCHMARK_TTL_SECONDS,
        refresh_ttl=ActionGroup.all(for_ttl=True),
    )


# TTL-cascade benchmark models: exercise aset_ttl(cascade=True) (real-Redis-7+ only).

BENCHMARK_CASCADE_DEPTH = 10
BENCHMARK_CASCADE_LIST_SIZE = 10


class BenchCascadeChild(AtomicRedisModel):
    """Plain cascade leaf shared by the two-FK and list-of-FK roots."""

    name: str = "child"

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=BENCHMARK_TTL_SECONDS)


class BenchCascadeTwoFkRoot(AtomicRedisModel):
    """Root with two cascade-enabled FK fields (the minimal cascade fan-out)."""

    name: str = "root"
    first: Annotated[Reference[BenchCascadeChild], CascadeTTL()]
    second: Annotated[Reference[BenchCascadeChild], CascadeTTL()]

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=BENCHMARK_TTL_SECONDS)


class BenchCascadeChainNode(AtomicRedisModel):
    """
    Self-referencing chain node whose ``next`` cascades one hop deeper.

    The marker lives on the field (not ``Meta.cascade_ttl``) because
    ``init_rapyer()`` resets every model's blanket ``Meta.cascade_ttl`` to None
    unless it is passed explicitly, and the benchmark conftest calls
    ``init_rapyer(redis=...)`` with no cascade arg. A per-field marker survives
    that reset, so the whole chain is walked regardless of length.
    """

    name: str = "node"
    next: Annotated[Optional[Reference["BenchCascadeChainNode"]], CascadeTTL()] = None

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=BENCHMARK_TTL_SECONDS)


class BenchCascadeListRoot(AtomicRedisModel):
    """Root holding a cascade-enabled list of many FK references."""

    name: str = "root"
    children: Annotated[list[Reference[BenchCascadeChild]], CascadeTTL()] = Field(
        default_factory=list
    )

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=BENCHMARK_TTL_SECONDS)


# Env-overridable so a constrained runner can dial the ~1M-node cascade walks down.
BENCHMARK_CASCADE_LARGE_SIZE = int(os.getenv("BENCHMARK_CASCADE_LARGE_SIZE", "1000000"))
BENCHMARK_CASCADE_LARGE_BRANCH = 10


class BenchCascadeLargeLeaf(AtomicRedisModel):
    """Edge-free leaf: a reached child costing one EXPIRE and no JSON.GET."""

    name: str = "leaf"

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=BENCHMARK_TTL_SECONDS)


class BenchCascadeLargeFanRoot(AtomicRedisModel):
    """Wide and shallow: one root referencing every leaf in a single hop."""

    name: str = "root"
    children: Annotated[list[Reference[BenchCascadeLargeLeaf]], CascadeTTL()] = Field(
        default_factory=list
    )

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=BENCHMARK_TTL_SECONDS)


class BenchCascadeLargeChainNode(AtomicRedisModel):
    """Narrow and deep: one hop per node, so the walk is pure traversal depth."""

    name: str = "node"
    next: Annotated[Optional[Reference["BenchCascadeLargeChainNode"]], CascadeTTL()] = (
        None
    )

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=BENCHMARK_TTL_SECONDS)


class BenchCascadeLargeTreeNode(AtomicRedisModel):
    """Branching: every interior node pays its own JSON.GET, the mageflow shape."""

    name: str = "node"
    children: Annotated[list[Reference["BenchCascadeLargeTreeNode"]], CascadeTTL()] = (
        Field(default_factory=list)
    )

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=BENCHMARK_TTL_SECONDS)
