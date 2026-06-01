from abc import ABC

import rapyer
from rapyer.base import AtomicRedisModel
from rapyer.types.base import RedisType
from tests.integration.actions.read import ReadActionTestBase
from tests.integration.actions.ttl import TTLActionTestBase
from tests.integration.functioninality.assertions import (
    assert_all_round_trip,
    assert_atomic_models_equal,
)
from tests.integration.special_types.adapters import SPECIAL_FIELD_ADAPTERS
from tests.models.collection_types import ComprehensiveTestModel


class FullModelReadBase(ReadActionTestBase, TTLActionTestBase, ABC):
    """
    Read actions that return a whole model. Verifies every field round-trips
    (plain fields, and special fields including nested ones) rather than just a
    couple of scalars.
    """

    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"
    skip_stale_mirror_in_pipeline = (
        "atomic read action; no field-level local mirror to corrupt"
    )

    def create_models(self):
        return [
            ComprehensiveTestModel(
                name="test", counter=1, tags=["t1"], metadata={"k": "v"}
            )
        ]

    async def setup_data(self):
        models = self.create_models()
        await rapyer.ainsert(*models)
        for adapter in SPECIAL_FIELD_ADAPTERS:
            await adapter.populate(models[0])
        return models

    def expected_before(self):
        return self.created_models[0]

    async def assert_action_effect(self, loaded, action_result):
        await assert_atomic_models_equal(action_result, self.created_models[0])


class FullModelFindManyBase(FullModelReadBase, ABC):
    """Read actions that return a list of models (afind)."""

    def expected_before(self):
        return [self.created_models[0]]

    async def assert_action_effect(self, loaded, action_result):
        await assert_all_round_trip(action_result, self.created_models)


class TestModelAget(FullModelReadBase):
    covered_method = AtomicRedisModel.aget

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await type(self.created_models[0]).aget(self.created_models[0].key)


class TestModelAload(FullModelReadBase):
    covered_method = AtomicRedisModel.aload

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await self.created_models[0].aload()


class TestModelAfind(FullModelFindManyBase):
    covered_method = AtomicRedisModel.afind

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await type(self.created_models[0]).afind()


class TestModelAfindOne(FullModelReadBase):
    covered_method = AtomicRedisModel.afind_one

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await type(self.created_models[0]).afind_one()


class TestRedisTypeAload(ReadActionTestBase, TTLActionTestBase):
    covered_method = RedisType.aload
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"
    skip_stale_mirror_in_pipeline = (
        "atomic read action; no field-level local mirror to corrupt"
    )

    def create_models(self):
        return [ComprehensiveTestModel(counter=42)]

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await self.created_models[0].counter.aload()

    def expected_before(self):
        return 42


class TestRapyerFunctionAget(FullModelReadBase):
    covered_method = rapyer.aget

    async def perform_action(self, piped):
        return await rapyer.aget(self.created_models[0].key)


class TestRapyerFunctionAfindOne(FullModelReadBase):
    covered_method = rapyer.afind_one

    async def perform_action(self, piped):
        return await rapyer.afind_one(self.created_models[0].key)


class TestRapyerFunctionAfind(FullModelFindManyBase):
    covered_method = rapyer.afind

    async def perform_action(self, piped):
        return await rapyer.afind(self.created_models[0].key)
