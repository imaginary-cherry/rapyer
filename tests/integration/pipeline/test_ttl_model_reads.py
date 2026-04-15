from rapyer.base import AtomicRedisModel
from rapyer.types.base import RedisType
from tests.integration.pipeline.pipeline_atomicity_base import (
    AsyncActionTestBase,
    AsyncComprehensiveCounterOpBase,
)
from tests.models.collection_types import (
    ComprehensiveTestModel,
    NoRefreshTTLComprehensiveTestModel,
    TTLComprehensiveTestModel,
)


class TestModelAget(AsyncActionTestBase):
    covered_method = AtomicRedisModel.aget
    ttl_model_cls = TTLComprehensiveTestModel
    no_refresh_ttl_model_cls = NoRefreshTTLComprehensiveTestModel
    skip_pipeline_atomicity = True

    def create_models(self):
        return [ComprehensiveTestModel(name="test", counter=1)]

    async def perform_action(self, piped: ComprehensiveTestModel) -> None:
        model = self.created_models[0]
        await type(model).aget(model.key)


class TestModelAload(AsyncActionTestBase):
    covered_method = AtomicRedisModel.aload
    ttl_model_cls = TTLComprehensiveTestModel
    no_refresh_ttl_model_cls = NoRefreshTTLComprehensiveTestModel
    skip_pipeline_atomicity = True

    def create_models(self):
        return [ComprehensiveTestModel(name="test", counter=1)]

    async def perform_action(self, piped: ComprehensiveTestModel) -> None:
        await self.created_models[0].aload()


class TestModelAfind(AsyncActionTestBase):
    covered_method = AtomicRedisModel.afind
    ttl_model_cls = TTLComprehensiveTestModel
    no_refresh_ttl_model_cls = NoRefreshTTLComprehensiveTestModel
    skip_pipeline_atomicity = True

    def create_models(self):
        return [ComprehensiveTestModel(name="test", counter=1)]

    async def perform_action(self, piped: ComprehensiveTestModel) -> None:
        await type(self.created_models[0]).afind()


class TestModelAfindOne(AsyncActionTestBase):
    covered_method = AtomicRedisModel.afind_one
    ttl_model_cls = TTLComprehensiveTestModel
    no_refresh_ttl_model_cls = NoRefreshTTLComprehensiveTestModel
    skip_pipeline_atomicity = True

    def create_models(self):
        return [ComprehensiveTestModel(name="test", counter=1)]

    async def perform_action(self, piped: ComprehensiveTestModel) -> None:
        await type(self.created_models[0]).afind_one()


class TestRedisTypeAload(AsyncComprehensiveCounterOpBase):
    covered_method = RedisType.aload
    skip_pipeline_atomicity = True

    def create_models(self):
        return [ComprehensiveTestModel(counter=42)]

    async def perform_action(self, piped: ComprehensiveTestModel) -> None:
        await self.created_models[0].counter.aload()

    def expected_before(self):
        return 42

    def expected_after(self):
        return 42
