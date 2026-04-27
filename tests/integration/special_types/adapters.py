from abc import ABC, abstractmethod
from typing import ClassVar

from redis import Redis

from rapyer.base import AtomicRedisModel
from tests.models.collection_types import ComprehensiveTestModel


class SpecialFieldAdapter(ABC):
    """
    An adapter for speical field to help us tests them for each action we need
    """

    sf_name: ClassVar[str]
    sp_field_class: ClassVar[type[AtomicRedisModel]]

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
    sf_name = "PrioirtyQueue"
    sp_field_class = ComprehensiveTestModel
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
