import rapyer
from rapyer import DeleteResult
from rapyer.base import AtomicRedisModel
from tests.integration.actions.base import ActionTestBase
from tests.integration.actions.two_model_delete import TwoModelDeleteBase
from tests.models.collection_types import ComprehensiveTestModel


class TestRapyerDelete(TwoModelDeleteBase):
    covered_method = AtomicRedisModel.adelete
    skip_ttl_refresh = "Nothing to refresh when model is deleted"
    skip_ttl_no_refresh = "Nothing to refresh when model is deleted"

    async def perform_action(self, piped):
        model1, _ = self.created_models
        await model1.adelete()


class TestRapyerDeleteByKey(TwoModelDeleteBase):
    covered_method = AtomicRedisModel.adelete_by_key
    skip_ttl_refresh = "Nothing to refresh when model is deleted"
    skip_ttl_no_refresh = "Nothing to refresh when model is deleted"

    async def perform_action(self, piped):
        model1, _ = self.created_models
        await type(model1).adelete_by_key(model1.key)


class TestModelAdeleteMany(ActionTestBase):
    covered_method = AtomicRedisModel.adelete_many

    def create_models(self):
        return [
            ComprehensiveTestModel(name="model1"),
            ComprehensiveTestModel(name="model2"),
            ComprehensiveTestModel(name="model3"),
        ]

    async def perform_action(self, piped):
        _model1, model2, model3 = self.created_models
        await type(model2).adelete_many(model2, model3)

    async def load_data(self):
        _model1, model2, model3 = self.created_models
        return (
            await self.real_redis_client.exists(model2.key),
            await self.real_redis_client.exists(model3.key),
        )

    def expected_before(self):
        return 1, 1

    def expected_after(self):
        return 0, 0


class TestRapyerAdeleteMany(ActionTestBase):
    covered_method = AtomicRedisModel.adelete_many

    result: DeleteResult | None = None

    def create_models(self):
        return [
            ComprehensiveTestModel(name="model1", tags=["a"]),
            ComprehensiveTestModel(name="model2", tags=["b"]),
        ]

    async def perform_action(self, piped):
        model1, model2 = self.created_models
        self.result = await ComprehensiveTestModel.adelete_many(model1, model2)

    async def load_data(self):
        model1, model2 = self.created_models
        return (
            await self.real_redis_client.exists(model1.key),
            await self.real_redis_client.exists(model2.key),
        )

    def expected_before(self):
        return 1, 1

    def expected_after(self):
        return 0, 0

    def assert_after_pipeline(self, loaded):
        super().assert_after_pipeline(loaded)
        assert isinstance(self.result, DeleteResult)
        assert self.result.models_deleted == 2


class TestRapyerFunctionAdeleteMany(ActionTestBase):
    covered_method = rapyer.adelete_many

    def create_models(self):
        return [
            ComprehensiveTestModel(name="s1"),
            ComprehensiveTestModel(counter=1),
        ]

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


class TestDelete(TwoModelDeleteBase):
    covered_method = AtomicRedisModel.adelete
    skip_ttl_refresh = "Nothing to refresh when model is deleted"
    skip_ttl_no_refresh = "Nothing to refresh when model is deleted"

    async def perform_action(self, piped):
        await piped.adelete()


class TestTryDelete(TwoModelDeleteBase):
    covered_method = AtomicRedisModel.adelete_by_key
    skip_ttl_refresh = "Nothing to refresh when model is deleted"
    skip_ttl_no_refresh = "Nothing to refresh when model is deleted"

    async def perform_action(self, piped):
        model1, _model2 = self.created_models
        await type(model1).adelete_by_key(model1.key)
