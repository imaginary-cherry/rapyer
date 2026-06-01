from abc import ABC, abstractmethod
from typing import ClassVar

from redis import Redis

import rapyer
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

    @abstractmethod
    async def assert_field_equal(
        self, actual: SpecialFieldType, expected: SpecialFieldType
    ) -> None:
        """Assert two instances of this adapter's special-field type hold equal content."""


class PriorityQueueAdapter(SpecialFieldAdapter):
    sf_class = RedisPriorityQueue
    EXPECTED_SIZE = 3

    def _queue_specs(self, model: ComprehensiveTestModel):
        """Each queue with type-appropriate sample items: the top-level queue
        holds ``int`` values, the nested one holds ``float`` values."""
        return [
            (model.tasks, [(10, 1.0), (20, 2.0), (30, 3.0)]),
            (model.container.tasks, [(1.5, 1.0), (2.5, 2.0), (3.5, 3.0)]),
        ]

    def additional_ttl_keys(self, model: ComprehensiveTestModel) -> list[str]:
        return [pq.special_key for pq, _ in self._queue_specs(model)]

    async def populate(self, model: ComprehensiveTestModel) -> None:
        # Batch the pushes: reuse an open pipeline if the caller already started
        # one, otherwise open a fresh pipeline so all pushes go in one round-trip.
        async with rapyer.apipeline(use_existing_pipe=True):
            for pq, items in self._queue_specs(model):
                for value, priority in items:
                    await pq.apush(value, priority)

    async def assert_data_present_by_key(self, model: ComprehensiveTestModel):
        for pq, _ in self._queue_specs(model):
            sp_key = pq.special_key
            size = await self.redis_client.zcard(sp_key)
            assert (
                size == self.EXPECTED_SIZE
            ), f"PQ key {sp_key} has {size} items; expected {self.EXPECTED_SIZE}"

    async def assert_data_absent_by_key(self, model: ComprehensiveTestModel):
        for pq, _ in self._queue_specs(model):
            sp_key = pq.special_key
            exists = await self.redis_client.exists(sp_key)
            assert not exists, f"PQ key {sp_key} unexpectedly still exists"

    async def assert_field_equal(
        self, actual: RedisPriorityQueue, expected: RedisPriorityQueue
    ) -> None:
        # The queue keeps no in-memory mirror, so compare the items stored in
        # Redis under each field's special key.
        actual_items = await actual.aitems()
        expected_items = await expected.aitems()
        assert actual_items == expected_items, (
            f"PQ {actual.special_key} differs from {expected.special_key}: "
            f"{actual_items!r} != {expected_items!r}"
        )


class RedisSetAdapter(SpecialFieldAdapter):
    sf_class = RedisSet
    EXPECTED_SIZE = 3

    def additional_ttl_keys(self, model: ComprehensiveTestModel) -> list[str]:
        return [model.container.labels.special_key]

    async def populate(self, model: ComprehensiveTestModel) -> None:
        await model.container.labels.aadd_many(["alpha", "beta", "gamma"])

    async def assert_data_present_by_key(self, model: ComprehensiveTestModel):
        sp_key = model.container.labels.special_key
        size = await self.redis_client.scard(sp_key)
        assert (
            size == self.EXPECTED_SIZE
        ), f"Set key {sp_key} has {size} items; expected {self.EXPECTED_SIZE}"

    async def assert_data_absent_by_key(self, model: ComprehensiveTestModel):
        sp_key = model.container.labels.special_key
        exists = await self.redis_client.exists(sp_key)
        assert not exists, f"Set key {sp_key} unexpectedly still exists"

    async def assert_field_equal(
        self, actual: RedisSet, expected: RedisSet
    ) -> None:
        # ``RedisSet`` is a ``set`` subclass with a faithful in-memory mirror,
        # so compare members directly.
        actual_members = set(actual)
        expected_members = set(expected)
        assert actual_members == expected_members, (
            f"RedisSet {actual.special_key} differs: "
            f"{actual_members!r} != {expected_members!r}"
        )


SPECIAL_FIELD_ADAPTERS = [PriorityQueueAdapter(), RedisSetAdapter()]
