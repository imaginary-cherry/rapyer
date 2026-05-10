from abc import ABC, abstractmethod
from typing import ClassVar

from redis import Redis

from rapyer.base import AtomicRedisModel
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.redis_set import RedisSet
from rapyer.types.special import SpecialFieldType
from tests.models.collection_types import ComprehensiveTestModel


class SpecialFieldAdapter(ABC):
    """
    An adapter for special field to help us tests them for each action we need
    """

    sf_class: ClassVar[type[SpecialFieldType]]

    @property
    def redis_client(self) -> Redis:
        return AtomicRedisModel.Meta.redis

    async def set_ttl(self, model: AtomicRedisModel, ttl: int):
        async with self.redis_client.pipeline() as pipe:
            for key in self.additional_ttl_keys(model):
                pipe.expire(key, ttl)
            await pipe.execute()

    async def get_additional_ttl(self, model: AtomicRedisModel) -> list[int]:
        ttls = []
        for key in self.additional_ttl_keys(model):
            ttls.append(await self.redis_client.ttl(key))
        return ttls

    @abstractmethod
    def additional_ttl_keys(self, model: AtomicRedisModel) -> list[str]: ...

    @abstractmethod
    async def populate(self, model: AtomicRedisModel) -> None: ...

    @abstractmethod
    async def assert_data_present_by_key(self, model: AtomicRedisModel): ...

    @abstractmethod
    async def assert_data_absent_by_key(self, model: AtomicRedisModel): ...


class PriorityQueueAdapter(SpecialFieldAdapter):
    sf_class = RedisPriorityQueue
    EXPECTED_SIZE = 3

    def additional_ttl_keys(self, model: ComprehensiveTestModel) -> list[str]:
        return [model.tasks.special_key]

    async def populate(self, model: ComprehensiveTestModel) -> None:
        await model.tasks.apush("high", 1.0)
        await model.tasks.apush("medium", 2.0)
        await model.tasks.apush("low", 3.0)

    async def assert_data_present_by_key(self, model: ComprehensiveTestModel):
        sp_key = model.tasks.special_key
        size = await self.redis_client.zcard(sp_key)
        assert (
            size == self.EXPECTED_SIZE
        ), f"PQ key {sp_key} has {size} items; expected {self.EXPECTED_SIZE}"

    async def assert_data_absent_by_key(self, model: ComprehensiveTestModel):
        sp_key = model.tasks.special_key
        exists = await self.redis_client.exists(sp_key)
        assert not exists, f"PQ key {sp_key} unexpectedly still exists"


class RedisSetAdapter(SpecialFieldAdapter):
    sf_class = RedisSet
    EXPECTED_SIZE = 3

    def additional_ttl_keys(self, model: ComprehensiveTestModel) -> list[str]:
        return [model.labels.special_key]

    async def populate(self, model: ComprehensiveTestModel) -> None:
        await model.labels.aadd_many(["alpha", "beta", "gamma"])

    async def assert_data_present_by_key(self, model: ComprehensiveTestModel):
        sp_key = model.labels.special_key
        size = await self.redis_client.scard(sp_key)
        assert (
            size == self.EXPECTED_SIZE
        ), f"Set key {sp_key} has {size} items; expected {self.EXPECTED_SIZE}"

    async def assert_data_absent_by_key(self, model: ComprehensiveTestModel):
        sp_key = model.labels.special_key
        exists = await self.redis_client.exists(sp_key)
        assert not exists, f"Set key {sp_key} unexpectedly still exists"


SPECIAL_FIELD_ADAPTERS = [PriorityQueueAdapter(), RedisSetAdapter()]
