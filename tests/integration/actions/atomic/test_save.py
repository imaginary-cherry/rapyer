import pytest

from rapyer.base import AtomicRedisModel
from tests.integration.actions.base import ActionTestBase
from tests.integration.actions.create import CreateActionTestBase
from tests.integration.actions.update import UpdateActionTestBase
from tests.integration.functioninality.assertions import assert_atomic_models_equal
from tests.models.collection_types import ComprehensiveTestModel


class TestModelAsave(UpdateActionTestBase, CreateActionTestBase):
    covered_method = AtomicRedisModel.asave
    skip_stale_mirror_in_pipeline = (
        "atomic asave writes the whole model; no field-level local mirror to corrupt"
    )

    def create_models(self):
        return [
            self.build_model(
                name="original", counter=10, tags=["t1"], metadata={"k": "v"}
            )
        ]

    async def perform_action(self, piped: ComprehensiveTestModel) -> None:
        piped.name = "updated"
        piped.counter = 99
        await piped.asave()

    async def load_data(self):
        return await ComprehensiveTestModel.aget(self.created_models[0].key)

    def assert_during_pipeline(self, loaded):
        # asave is deferred inside the pipeline: the persisted model is still
        # at its pre-action values.
        assert loaded.name == "original" and loaded.counter == 10

    async def assert_after_pipeline(self, loaded):
        # The whole model (every field, special fields included) round-trips.
        await assert_atomic_models_equal(loaded, self.created_models[0])

    async def assert_action_effect(self, loaded, action_result):
        await assert_atomic_models_equal(loaded, self.created_models[0])

    @pytest.mark.asyncio
    async def test_no_clobber_effect_when_outside_of_pipeline(self, test_input):
        pytest.skip(
            "Asave saves the entire model, there is no point in checking the clobber"
        )


class TestRapyerAsaveBatching(ActionTestBase):
    covered_method = AtomicRedisModel.asave
    skip_stale_mirror_in_pipeline = (
        "atomic asave writes the whole model; no field-level local mirror to corrupt"
    )

    def create_models(self):
        return [
            ComprehensiveTestModel(name="model1", counter=1, tags=["tag1"]),
            ComprehensiveTestModel(name="model2", counter=2, tags=["tag2"]),
            ComprehensiveTestModel(name="model3", counter=3, tags=["tag3"]),
        ]

    async def setup_data(self):
        # Don't pre-insert — the asave calls inside the pipeline are the subject.
        return self.create_models()

    async def perform_action(self, piped):
        for model in self.created_models:
            await model.asave()

    async def load_data(self):
        return tuple(
            [await self.real_redis_client.exists(m.key) for m in self.created_models]
        )

    def expected_before(self):
        return 0, 0, 0

    def expected_after(self):
        return 1, 1, 1
