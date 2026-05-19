from datetime import datetime
from typing import ClassVar, Dict, List

from pydantic import Field

from rapyer.actions import ActionGroup
from rapyer.base import AtomicRedisModel
from rapyer.config import RedisConfig
from rapyer.types import RedisDatetimeTimestamp
from tests.models.collection_types import SimpleListModel, StrDictModel
from tests.models.index_types import IndexTestModel
from tests.models.redis_types import DirectRedisIntModel
from tests.models.simple_types import FloatModel, IntModel, StrModel
from tests.models.special_types import GenericRedisSetModel, PriorityQueueModel

BENCHMARK_TTL_SECONDS = 3600


class BenchmarkPipelineModel(AtomicRedisModel):
    """Scalar/list/dict-only model for pipeline benchmarks.

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
