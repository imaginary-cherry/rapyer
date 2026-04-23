import asyncio

import rapyer
from tests.integration.pipeline.pipeline_atomicity_base import (
    ActionTestBase,
    TTLActionTestBase,
    UpdateActionTestBase,
)
from tests.models.collection_types import ComprehensiveTestModel
from tests.models.simple_types import IntModel, StrModel


class TestRapyerFunctionAdeleteMany(ActionTestBase):
    covered_method = rapyer.adelete_many

    def create_models(self):
        return [StrModel(name="s1"), IntModel(count=1)]

    async def perform_action(self, piped):
        await rapyer.adelete_many(*self.created_models)

    async def load_data(self):
        return tuple(
            [await self.real_redis_client.exists(m.key) for m in self.created_models]
        )

    def expected_before(self):
        return 1, 1

    def expected_after(self):
        return 0, 0


class TestRapyerFunctionAinsert(TTLActionTestBase):
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


class TestRapyerFunctionApipeline(TTLActionTestBase, UpdateActionTestBase):
    covered_method = rapyer.apipeline

    def create_models(self):
        return [ComprehensiveTestModel(name="original")]

    async def perform_action(self, piped):
        async with rapyer.apipeline(use_existing_pipe=True):
            piped.name = "updated"
            await piped.asave()

    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.created_models[0].key)
        return loaded.name

    def expected_before(self):
        return "original"

    def expected_after(self):
        return "updated"


class TestRapyerFunctionAget(TTLActionTestBase, UpdateActionTestBase):
    covered_method = rapyer.aget
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    def create_models(self):
        return [ComprehensiveTestModel(name="aget-target")]

    async def perform_action(self, piped):
        assert await rapyer.aget(self.created_models[0].key) is not None


class TestRapyerFunctionAfindOne(TTLActionTestBase, UpdateActionTestBase):
    covered_method = rapyer.afind_one
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    def create_models(self):
        return [ComprehensiveTestModel(name="afind-one-target")]

    async def perform_action(self, piped):
        assert await rapyer.afind_one(self.created_models[0].key) is not None


class TestRapyerFunctionAfind(TTLActionTestBase, UpdateActionTestBase):
    covered_method = rapyer.afind
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    def create_models(self):
        return [ComprehensiveTestModel(name="afind-target")]

    async def perform_action(self, piped):
        results = await rapyer.afind(self.created_models[0].key)
        assert len(results) == 1
