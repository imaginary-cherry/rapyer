from abc import ABC
from typing import ClassVar

from rapyer.types.priority_queue import PriorityQueueItem, RedisPriorityQueue
from tests.integration.pipeline.pipeline_atomicity_base import (
    AsyncActionTestBase,
    UpdateActionTestBase,
)
from tests.models.special_types import PriorityQueueModel

# Initial items every PQ test class starts with. Kept in class-level constants
# so test classes can assemble their ``expected_before`` / ``expected_after``
# from them without re-declaring the serialized form inline.
INITIAL_ITEMS: list[tuple[str, float]] = [
    ("high", 1.0),
    ("medium", 2.0),
    ("low", 3.0),
]
# Serialized form returned by ZRANGE (JSON-encoded member + float score).
INITIAL_CONTENTS: list[tuple[str, float]] = [
    ('"high"', 1.0),
    ('"medium"', 2.0),
    ('"low"', 3.0),
]


class PQActionBase(UpdateActionTestBase, AsyncActionTestBase, ABC):
    initial_items: ClassVar[list[tuple[str, float]]] = INITIAL_ITEMS

    def create_models(self):
        return [PriorityQueueModel(name="pq_test")]

    def ttl_keys(self, model: PriorityQueueModel):
        return [model.key, model.tasks.special_key]

    async def setup_data(self):
        """Insert the model AND populate the PQ special field with
        ``initial_items`` so actions run against a non-empty queue."""
        models = await super().setup_data()
        for inst in models:
            for value, priority in self.initial_items:
                await inst.tasks.apush(value, priority)
        return models

    async def load_data(self):
        return await self.real_redis_client.zrange(
            self.created_models[0].tasks.special_key, 0, -1, withscores=True
        )


class TestPQApush(PQActionBase):
    covered_method = RedisPriorityQueue.apush

    async def perform_action(self, piped: PriorityQueueModel):
        await piped.tasks.apush("new_item", 0.5)

    def expected_before(self):
        return INITIAL_CONTENTS

    def expected_after(self):
        # priority 0.5 < 1.0, so the new item sorts in front of the initial trio.
        return [('"new_item"', 0.5), *INITIAL_CONTENTS]


class TestPQApushMany(PQActionBase):
    covered_method = RedisPriorityQueue.apush_many

    async def perform_action(self, piped: PriorityQueueModel):
        await piped.tasks.apush_many(
            [
                PriorityQueueItem(value="a", priority=0.1),
                PriorityQueueItem(value="b", priority=0.2),
            ]
        )

    def expected_before(self):
        return INITIAL_CONTENTS

    def expected_after(self):
        return [('"a"', 0.1), ('"b"', 0.2), *INITIAL_CONTENTS]


class TestPQAclear(PQActionBase):
    covered_method = RedisPriorityQueue.aclear

    def ttl_keys(self, model):
        return [model.key]

    async def perform_action(self, piped: PriorityQueueModel):
        await piped.tasks.aclear()

    def expected_before(self):
        return INITIAL_CONTENTS

    def expected_after(self):
        return []


class TestPQApop(PQActionBase):
    covered_method = RedisPriorityQueue.apop
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    async def perform_action(self, piped: PriorityQueueModel):
        await self.created_models[0].tasks.apop()


class TestPQAremove(PQActionBase):
    covered_method = RedisPriorityQueue.aremove

    async def perform_action(self, piped: PriorityQueueModel):
        await self.created_models[0].tasks.aremove("medium")


class TestPQApeek(PQActionBase):
    covered_method = RedisPriorityQueue.apeek
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    async def perform_action(self, piped: PriorityQueueModel):
        await self.created_models[0].tasks.apeek()


class TestPQAsize(PQActionBase):
    covered_method = RedisPriorityQueue.asize
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    async def perform_action(self, piped: PriorityQueueModel):
        await self.created_models[0].tasks.asize()


class TestPQAitems(PQActionBase):
    covered_method = RedisPriorityQueue.aitems
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    async def perform_action(self, piped: PriorityQueueModel):
        await self.created_models[0].tasks.aitems()
