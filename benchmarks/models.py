from typing import ClassVar

from rapyer.actions import ActionGroup
from rapyer.config import RedisConfig
from tests.models.collection_types import SimpleListModel, StrDictModel
from tests.models.index_types import IndexTestModel
from tests.models.redis_types import DirectRedisIntModel
from tests.models.simple_types import FloatModel, IntModel, StrModel
from tests.models.special_types import PriorityQueueModel

BENCHMARK_TTL_SECONDS = 3600


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
