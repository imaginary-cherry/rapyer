import asyncio

import rapyer
from rapyer.base import AtomicRedisModel
from tests.integration.actions.async_action import AsyncActionTestBase
from tests.integration.actions.create import CreateActionTestBase
from tests.integration.functioninality.assertions import assert_all_round_trip
from tests.models.collection_types import ComprehensiveTestModel


class TestModelAinsert(CreateActionTestBase):
    covered_method = AtomicRedisModel.ainsert
    model_exists_before_action = False
    skip_ttl_no_refresh = "Ainsert is initial so we always set ttl"
    skip_stale_mirror_in_pipeline = (
        "atomic ainsert; no field-level local mirror to corrupt"
    )

    def create_models(self):
        # The ``ainsert`` call is the test subject; the SF is assigned in-memory.
        return [
            self.build_model(name="existing", counter=1, tags=["a"]),
            self.build_model(name="existing2", counter=2, tags=["b"]),
        ]

    async def setup_data(self):
        models = self.create_models()
        return models

    async def perform_action(self, piped: ComprehensiveTestModel):
        await type(self.created_models[0]).ainsert(*self.created_models)

    async def load_data(self):
        existing_data = await asyncio.gather(
            *[rapyer.afind_one(model.key) for model in self.created_models]
        )
        return [data for data in existing_data if data is not None]

    def expected_before(self):
        return []

    async def assert_after_pipeline(self, loaded):
        await assert_all_round_trip(loaded, self.created_models)

    async def assert_action_effect(self, loaded, action_result):
        await assert_all_round_trip(loaded, self.created_models)


class TestRapyerAinsert(AsyncActionTestBase):
    covered_method = AtomicRedisModel.ainsert
    skip_stale_mirror_in_pipeline = (
        "atomic ainsert; no field-level local mirror to corrupt"
    )

    def create_models(self):
        return [
            ComprehensiveTestModel(name="model1"),
            ComprehensiveTestModel(name="model2"),
        ]

    async def setup_data(self):
        # Don't pre-insert — the ``ainsert`` call inside the pipeline is the
        # test subject, so ``handle`` is the (unsaved) models themselves.
        return self.create_models()

    async def perform_action(self, piped):
        await type(self.created_models[0]).ainsert(*self.created_models)

    async def load_data(self):
        return tuple(
            [await self.real_redis_client.exists(m.key) for m in self.created_models]
        )

    def expected_before(self):
        return 0, 0

    def expected_after(self):
        return 1, 1


class TestRapyerFunctionAinsert(CreateActionTestBase):
    covered_method = rapyer.ainsert
    model_exists_before_action = False
    skip_ttl_no_refresh = "Ainsert is initial so we always set ttl"
    skip_stale_mirror_in_pipeline = (
        "module-level rapyer.ainsert; no field-level local mirror to corrupt"
    )

    def create_models(self):
        return [
            self.build_model(name="to_insert1", counter=1, tags=["a"]),
            self.build_model(name="to_insert2", counter=2, tags=["b"]),
        ]

    async def setup_data(self):
        models = self.create_models()
        return models

    async def perform_action(self, piped):
        await rapyer.ainsert(*self.created_models)

    async def load_data(self):
        found = await asyncio.gather(
            *[rapyer.afind_one(m.key) for m in self.created_models]
        )
        return [m for m in found if m is not None]

    def expected_before(self):
        return []

    async def assert_after_pipeline(self, loaded):
        await assert_all_round_trip(loaded, self.created_models)

    async def assert_action_effect(self, loaded, action_result):
        await assert_all_round_trip(loaded, self.created_models)
