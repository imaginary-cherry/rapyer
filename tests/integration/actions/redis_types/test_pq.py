from abc import ABC
from typing import ClassVar

from rapyer.types.priority_queue import PriorityQueueItem, RedisPriorityQueue
from tests.integration.actions.read import ReadActionTestBase
from tests.integration.actions.ttl import TTLActionTestBase
from tests.integration.actions.update import UpdateActionTestBase
from tests.models.collection_types import ComprehensiveTestModel

# Initial items every PQ test class starts with. Kept in class-level constants
# so test classes can assemble their ``expected_before`` / ``expected_after``
# from them without re-declaring the serialized form inline.
# ``ComprehensiveTestModel.tasks`` is a ``RedisPriorityQueue[int]``, so values
# are integers (their serialized ZSET member is the bare JSON number, e.g.
# ``json.dumps(10) == '10'`` — no quotes).
INITIAL_ITEMS: list[tuple[int, float]] = [
    (10, 1.0),
    (20, 2.0),
    (30, 3.0),
]
# Serialized form returned by ZRANGE (JSON-encoded member + float score).
INITIAL_CONTENTS: list[tuple[str, float]] = [
    ("10", 1.0),
    ("20", 2.0),
    ("30", 3.0),
]


class PQActionBase(UpdateActionTestBase, TTLActionTestBase, ABC):
    initial_items: ClassVar[list[tuple[int, float]]] = INITIAL_ITEMS
    skip_target_field_clobber_check = (
        "RedisPriorityQueue is a pure Redis proxy; no local state to mutate"
    )
    skip_stale_mirror_in_pipeline = (
        "RedisPriorityQueue is a pure Redis proxy; no local mirror to corrupt"
    )

    def create_models(self):
        return [ComprehensiveTestModel(name="pq_test")]

    def ttl_keys(self, model: ComprehensiveTestModel):
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

    def expected_before(self):
        return INITIAL_CONTENTS


class TestPQApush(PQActionBase):
    covered_method = RedisPriorityQueue.apush

    async def perform_action(self, piped: ComprehensiveTestModel):
        await piped.tasks.apush(40, 0.5)

    def expected_after(self):
        # priority 0.5 < 1.0, so the new item sorts in front of the initial trio.
        return [("40", 0.5), *INITIAL_CONTENTS]


class TestPQApushMany(PQActionBase):
    covered_method = RedisPriorityQueue.apush_many

    async def perform_action(self, piped: ComprehensiveTestModel):
        await piped.tasks.apush_many(
            [
                PriorityQueueItem(value=11, priority=0.1),
                PriorityQueueItem(value=12, priority=0.2),
            ]
        )

    def expected_before(self):
        return INITIAL_CONTENTS

    def expected_after(self):
        return [("11", 0.1), ("12", 0.2), *INITIAL_CONTENTS]


class TestPQAclear(PQActionBase):
    covered_method = RedisPriorityQueue.aclear

    def ttl_keys(self, model):
        return [model.key]

    async def perform_action(self, piped: ComprehensiveTestModel):
        await piped.tasks.aclear()

    def expected_before(self):
        return INITIAL_CONTENTS

    def expected_after(self):
        return []


class TestPQApop(ReadActionTestBase, PQActionBase):
    covered_method = RedisPriorityQueue.apop
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await self.created_models[0].tasks.apop()

    def expected_before(self):
        # apop returns the highest-priority value (the deserialized member).
        return INITIAL_ITEMS[0][0]


class TestPQAremove(PQActionBase):
    covered_method = RedisPriorityQueue.aremove

    async def perform_action(self, piped: ComprehensiveTestModel):
        await self.created_models[0].tasks.aremove(20)

    def expected_after(self):
        return [("10", 1.0), ("30", 3.0)]


class TestPQApeek(ReadActionTestBase, PQActionBase):
    covered_method = RedisPriorityQueue.apeek
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await self.created_models[0].tasks.apeek()

    def expected_before(self):
        return INITIAL_ITEMS[0][0]


class TestPQAsize(ReadActionTestBase, PQActionBase):
    covered_method = RedisPriorityQueue.asize
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await self.created_models[0].tasks.asize()

    def expected_before(self):
        return len(INITIAL_ITEMS)


class TestPQAitems(ReadActionTestBase, PQActionBase):
    covered_method = RedisPriorityQueue.aitems
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await self.created_models[0].tasks.aitems()

    def expected_before(self):
        return [
            PriorityQueueItem(value=value, priority=priority)
            for value, priority in INITIAL_ITEMS
        ]
