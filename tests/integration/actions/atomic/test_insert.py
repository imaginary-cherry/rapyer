import asyncio

import rapyer
from rapyer.base import AtomicRedisModel
from tests.integration.actions.base import ActionTestBase
from tests.integration.actions.create import CreateActionTestBase
from tests.models.collection_types import ComprehensiveTestModel


class TestModelAinsert(CreateActionTestBase):
    covered_method = AtomicRedisModel.ainsert
    model_exists_before_action = False
    skip_ttl_no_refresh = "Ainsert is initial so we always set ttl"

    def create_models(self):
        # Only the existing model is inserted; the new model is the test subject.
        return [
            ComprehensiveTestModel(name="existing"),
            ComprehensiveTestModel(name="existing2"),
        ]

    async def setup_data(self):
        return self.create_models()

    async def perform_action(self, piped: ComprehensiveTestModel):
        await type(self.created_models[0]).ainsert(*self.created_models)

    async def load_data(self):
        existing_data = await asyncio.gather(
            *[rapyer.afind_one(model.key) for model in self.created_models]
        )
        return [data for data in existing_data if data is not None]

    def expected_before(self):
        return []

    def expected_after(self):
        return self.created_models


class TestRapyerAinsert(ActionTestBase):
    covered_method = AtomicRedisModel.ainsert

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

    def create_models(self):
        return [
            ComprehensiveTestModel(name="to_insert1"),
            ComprehensiveTestModel(name="to_insert2"),
        ]

    async def setup_data(self):
        return self.create_models()

    async def perform_action(self, piped):
        await rapyer.ainsert(*self.created_models)

    async def load_data(self):
        found = await asyncio.gather(
            *[rapyer.afind_one(m.key) for m in self.created_models]
        )
        return [m for m in found if m is not None]

    def expected_before(self):
        return []

    def expected_after(self):
        return self.created_models
