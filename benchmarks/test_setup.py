from abc import ABC, abstractmethod
from datetime import datetime
from typing import ClassVar

import pytest
from pydantic import Field

from rapyer import AtomicRedisModel
from rapyer.base import REDIS_MODELS
from rapyer.config import RedisConfig
from rapyer.fields import Index, Key
from rapyer.init import init_rapyer
from rapyer.types import RedisDict, RedisInt, RedisList, RedisPriorityQueue

SHARED_NO_INIT_META = RedisConfig(init_with_rapyer=False)


class SetupBenchmarkTest(ABC):
    pytestmark = [pytest.mark.benchmark]
    rounds = 20

    @abstractmethod
    def declare_fn(self) -> list[type[AtomicRedisModel]]: ...

    def test_class_declaration(self, benchmark):
        benchmark.pedantic(self.declare_fn, rounds=self.rounds, iterations=1)

    def test_init_rapyer(self, benchmark, event_loop, redis_client):
        models = self.declare_fn()

        saved = REDIS_MODELS[:]
        REDIS_MODELS.clear()
        REDIS_MODELS.extend(models)
        try:

            def sync_action():
                event_loop.run_until_complete(init_rapyer(redis=redis_client))

            benchmark.pedantic(sync_action, rounds=self.rounds, iterations=1)
        finally:
            REDIS_MODELS.clear()
            REDIS_MODELS.extend(saved)


class TestSetupEmpty(SetupBenchmarkTest):
    def declare_fn(self) -> list[type[AtomicRedisModel]]:
        class EmptyModel(AtomicRedisModel):
            name: str = ""

            Meta: ClassVar[RedisConfig] = SHARED_NO_INIT_META

        return [EmptyModel]


class TestSetupPrimitives(SetupBenchmarkTest):
    def declare_fn(self) -> list[type[AtomicRedisModel]]:
        class PrimitivesModel(AtomicRedisModel):
            text: str = ""
            count: int = 0
            ratio: float = 0.0
            flag: bool = False
            blob: bytes = b""
            when: datetime = Field(default_factory=datetime.now)

            Meta: ClassVar[RedisConfig] = SHARED_NO_INIT_META

        return [PrimitivesModel]


class TestSetupCollections(SetupBenchmarkTest):
    def declare_fn(self) -> list[type[AtomicRedisModel]]:
        class CollectionsModel(AtomicRedisModel):
            tags: list[str] = Field(default_factory=list)
            settings: dict[str, str] = Field(default_factory=dict)

            Meta: ClassVar[RedisConfig] = SHARED_NO_INIT_META

        return [CollectionsModel]


class TestSetupWithKey(SetupBenchmarkTest):
    def declare_fn(self) -> list[type[AtomicRedisModel]]:
        class WithKeyModel(AtomicRedisModel):
            user_id: Key[str]
            name: str = ""

            Meta: ClassVar[RedisConfig] = SHARED_NO_INIT_META

        return [WithKeyModel]


class TestSetupWithIndex(SetupBenchmarkTest):
    def declare_fn(self) -> list[type[AtomicRedisModel]]:
        class WithIndexModel(AtomicRedisModel):
            name: Index[str]
            description: str = ""

            Meta: ClassVar[RedisConfig] = SHARED_NO_INIT_META

        return [WithIndexModel]


class TestSetupWithMultiIndex(SetupBenchmarkTest):
    def declare_fn(self) -> list[type[AtomicRedisModel]]:
        class WithMultiIndexModel(AtomicRedisModel):
            name: Index[str]
            age: Index[int]
            score: Index[float]
            created_at: Index[datetime]
            description: str = ""

            Meta: ClassVar[RedisConfig] = SHARED_NO_INIT_META

        return [WithMultiIndexModel]


class TestSetupWithNested(SetupBenchmarkTest):
    def declare_fn(self) -> list[type[AtomicRedisModel]]:
        class NestedAddress(AtomicRedisModel):
            street: str = ""
            city: str = ""

            Meta: ClassVar[RedisConfig] = SHARED_NO_INIT_META

        class NestedPerson(AtomicRedisModel):
            name: str = ""
            address: NestedAddress = Field(default_factory=NestedAddress)

            Meta: ClassVar[RedisConfig] = SHARED_NO_INIT_META

        return [NestedAddress, NestedPerson]


class TestSetupWithRedisTypes(SetupBenchmarkTest):
    def declare_fn(self) -> list[type[AtomicRedisModel]]:
        class WithRedisTypesModel(AtomicRedisModel):
            counter: RedisInt = 0
            items: RedisList[str] = Field(default_factory=list)
            settings: RedisDict[str] = Field(default_factory=dict)

            Meta: ClassVar[RedisConfig] = SHARED_NO_INIT_META

        return [WithRedisTypesModel]


class TestSetupWithPriorityQueue(SetupBenchmarkTest):
    def declare_fn(self) -> list[type[AtomicRedisModel]]:
        class WithPriorityQueueModel(AtomicRedisModel):
            name: str = ""
            tasks: RedisPriorityQueue[str] = Field(default_factory=RedisPriorityQueue)

            Meta: ClassVar[RedisConfig] = SHARED_NO_INIT_META

        return [WithPriorityQueueModel]


class TestSetupWithInheritance(SetupBenchmarkTest):
    def declare_fn(self) -> list[type[AtomicRedisModel]]:
        class InheritanceBase(AtomicRedisModel):
            name: str = ""
            age: int = 0

            Meta: ClassVar[RedisConfig] = SHARED_NO_INIT_META

        class InheritanceChild(InheritanceBase):
            role: str = ""
            permissions: list[str] = Field(default_factory=list)

        return [InheritanceBase, InheritanceChild]
