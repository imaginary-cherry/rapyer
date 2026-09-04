import hashlib
from typing import Annotated, ClassVar, Generic, Optional, TypeVar

from pydantic import Field

from rapyer.base import AtomicRedisModel, RedisConfig
from rapyer.fields.vector import Vector
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.redis_set import RedisSet
from rapyer.types.text import RedisText
from tests.models.simple_types import TTL_TEST_SECONDS

T = TypeVar("T")


class FakeTextEmbeddingAdapter:
    """Deterministic, network-free EmbeddingAdapter double for RedisText fixtures."""

    # Content-keyed vector: identical text always yields the identical vector.
    def __init__(self):
        self.call_count = 0

    @property
    def dims(self):
        return 3

    @property
    def label(self):
        return "fake-text-adapter@1:3"

    @staticmethod
    def _vector_for(content: str) -> list[float]:
        digest = hashlib.sha256(content.encode()).digest()
        return [digest[0] / 255.0, digest[1] / 255.0, digest[2] / 255.0]

    async def aembed(self, content: str) -> list[float]:
        return self._vector_for(content)

    async def aembed_many(self, contents: list[str]) -> list[list[float]]:
        self.call_count += 1
        return [self._vector_for(content) for content in contents]


class PriorityQueueModelBase(AtomicRedisModel, Generic[T]):
    tasks: RedisPriorityQueue[T] = Field(
        default_factory=RedisPriorityQueue, exclude=True
    )


class PriorityQueueModel(PriorityQueueModelBase[str]):
    name: str = "default"

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=TTL_TEST_SECONDS)


class PriorityQueueIntModel(PriorityQueueModelBase[int]):
    label: str = "test"


class MixedSpecialModel(PriorityQueueModelBase[str]):
    name: str = "mixed"
    count: int = 0


class OptionalPriorityQueueModel(AtomicRedisModel):
    name: str = "default"
    tasks: Optional[RedisPriorityQueue[str]] = Field(default=None, exclude=True)


class GenericPriorityQueueModel(AtomicRedisModel, Generic[T]):
    name: str = "default"
    tasks: RedisPriorityQueue[T] = Field(
        default_factory=RedisPriorityQueue, exclude=True
    )


class SubSubPriorityQueueModel(PriorityQueueModel):
    extra: str = "sub_sub"


class OverriddenSpecialFieldModel(PriorityQueueModelBase[str]):
    tasks: int = 0  # redefine inherited special field as non-special


class PQContainerModel(AtomicRedisModel):
    inner_pq: PriorityQueueModel = Field(default_factory=PriorityQueueModel)
    outer_name: str = "container"


class InnerSameNamePQModel(AtomicRedisModel):
    label: str = "inner"
    tasks: RedisPriorityQueue[str] = Field(
        default_factory=RedisPriorityQueue, exclude=True
    )


class NestedSameNamePQModel(AtomicRedisModel):
    name: str = "outer"
    tasks: RedisPriorityQueue[str] = Field(
        default_factory=RedisPriorityQueue, exclude=True
    )
    inner: InnerSameNamePQModel = Field(default_factory=InnerSameNamePQModel)


class GenericRedisSetModel(AtomicRedisModel, Generic[T]):
    name: str = "default"
    count: int = 0
    tags: RedisSet[T] = Field(default_factory=RedisSet)


class OptionalRedisSetModel(AtomicRedisModel):
    name: str = "default"
    tags: Optional[RedisSet[str]] = None


class AutoMappedSetModel(AtomicRedisModel):
    name: str = "default"
    tags: set[str] = Field(default_factory=set)


class SubSubRedisSetModel(GenericRedisSetModel[str]):
    extra: str = "sub_sub"


class RedisSetContainerModel(AtomicRedisModel):
    inner_set: GenericRedisSetModel[str] = Field(
        default_factory=GenericRedisSetModel[str]
    )
    outer_name: str = "container"


class ListOfSetsModel(AtomicRedisModel):
    # A plain list of bare SFs; the metaclass detects it via GenericRedisType.contains_sf_field.
    buckets: list[RedisSet] = Field(default_factory=list)


class RedisTextModel(AtomicRedisModel):
    name: str = "default"
    body: RedisText = Field(default_factory=lambda: RedisText(""))

    Meta: ClassVar[RedisConfig] = RedisConfig(vectorizer=FakeTextEmbeddingAdapter())


class VectorAnnotatedTextModel(AtomicRedisModel):
    name: str = "default"
    body: Annotated[RedisText, Vector(dim=3)] = Field(
        default_factory=lambda: RedisText("")
    )

    Meta: ClassVar[RedisConfig] = RedisConfig(vectorizer=FakeTextEmbeddingAdapter())
