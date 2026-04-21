from abc import ABC

import rapyer
from rapyer.types.priority_queue import PriorityQueueItem, RedisPriorityQueue
from tests.integration.conftest import REDUCED_TTL_SECONDS
from tests.integration.pipeline.pipeline_atomicity_base import (
    AsyncActionTestBase,
    UpdateActionTestBase,
)
from tests.models.special_types import (
    PriorityQueueModel,
    PriorityQueueTTLModel,
    PriorityQueueTTLNoRefreshModel,
)


class PQActionBase(UpdateActionTestBase, AsyncActionTestBase, ABC):
    ttl_model_cls = PriorityQueueTTLModel
    no_refresh_ttl_model_cls = PriorityQueueTTLNoRefreshModel
    skip_pipeline_atomicity = True

    def create_models(self):
        return [PriorityQueueModel(name="pq_test")]

    def ttl_keys(self, model: PriorityQueueModel):
        return [model.key, model.tasks.special_key]

    async def _setup_ttl_data(self, model_cls: type[PriorityQueueModel]):
        originals = self.create_models()
        recreated = [model_cls(**m.model_dump()) for m in originals]
        await rapyer.ainsert(*recreated)

        for inst in recreated:
            await inst.tasks.apush("high", 1.0)
            await inst.tasks.apush("medium", 2.0)
            await inst.tasks.apush("low", 3.0)

        for inst in recreated:
            for key in self.ttl_keys(inst):
                await self.real_redis_client.expire(key, REDUCED_TTL_SECONDS)

        return recreated


class TestPQApush(PQActionBase):
    covered_method = RedisPriorityQueue.apush

    async def perform_action(self, piped: PriorityQueueModel):
        await self.created_models[0].tasks.apush("new_item", 0.5)


class TestPQApushMany(PQActionBase):
    covered_method = RedisPriorityQueue.apush_many

    async def perform_action(self, piped: PriorityQueueModel):
        await self.created_models[0].tasks.apush_many(
            [
                PriorityQueueItem(value="a", priority=0.1),
                PriorityQueueItem(value="b", priority=0.2),
            ]
        )


class TestPQApop(PQActionBase):
    covered_method = RedisPriorityQueue.apop

    async def perform_action(self, piped: PriorityQueueModel):
        await self.created_models[0].tasks.apop()


class TestPQAremove(PQActionBase):
    covered_method = RedisPriorityQueue.aremove

    async def perform_action(self, piped: PriorityQueueModel):
        await self.created_models[0].tasks.aremove("medium")


class TestPQAclear(PQActionBase):
    """``aclear`` deletes the special key, so only check ``model.key`` TTL."""

    covered_method = RedisPriorityQueue.aclear

    def ttl_keys(self, model):
        return [model.key]

    async def perform_action(self, piped: PriorityQueueModel):
        await self.created_models[0].tasks.aclear()
