import pytest

from rapyer.base import AtomicRedisModel
from rapyer.types.dct import RedisDict
from rapyer.types.integer import RedisInt
from rapyer.types.lst import RedisList
from tests.integration.pipeline.pipeline_atomicity_base import (
    ActionTestBase,
    AsyncActionTestBase,
    AsyncComprehensiveCounterOpBase,
    ComprehensiveMetadataOpBase,
    ComprehensiveTagsOpBase,
    TwoModelDeleteBase,
    UpdateActionTestBase,
)
from tests.models.collection_types import ComprehensiveTestModel
from tests.models.simple_types import (
    TTL_TEST_SECONDS,
    TTLRefreshTestModel,
    UserModelWithoutTTL,
)

TTL_SECONDS = 300


class TestModelAsave(UpdateActionTestBase, AsyncActionTestBase):
    covered_method = AtomicRedisModel.asave

    def create_models(self):
        return [ComprehensiveTestModel(name="original", counter=10)]

    async def perform_action(self, piped: ComprehensiveTestModel) -> None:
        piped.name = "updated"
        piped.counter = 99
        await piped.asave()

    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.created_models[0].key)
        return loaded.name, loaded.counter

    def expected_before(self):
        return "original", 10

    def expected_after(self):
        return "updated", 99


class TestModelAinsert(AsyncActionTestBase):
    """Verify ``ainsert`` inside a model pipeline defers the new model's creation.

    ``ainsert`` is the only async action whose subject is a fresh (unsaved)
    model, so the standard ``_setup_ttl_data`` flow (pre-insert + reduce TTL)
    doesn't apply. The TTL tests are overridden to assert that the initial
    TTL set by ``asave`` matches the configured value.
    """

    covered_method = AtomicRedisModel.ainsert
    model_exists_before_action = False

    def create_models(self):
        # Only the existing model is inserted; the new model is the test subject.
        return [
            ComprehensiveTestModel(name="existing"),
            ComprehensiveTestModel(name="existing2"),
        ]

    async def setup_data(self):
        return self.create_models()

    async def perform_action(self, piped: ComprehensiveTestModel):
        await ComprehensiveTestModel.ainsert(*self.created_models)

    async def load_data(self):
        """Return ``(exists_flag, name_or_None)`` for the new model."""
        _existing, new_model = self.created_models
        exists = await self.real_redis_client.exists(new_model.key)
        if not exists:
            return 0, None
        loaded = await ComprehensiveTestModel.aget(new_model.key)
        return 1, loaded.name

    def expected_before(self):
        return 0, None

    def expected_after(self):
        return 1, "inserted"

    @pytest.mark.asyncio
    async def test_ttl_no_refresh_on_action(self):
        pytest.skip("Ainsert is initial so we always set ttl")



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
        await ComprehensiveTestModel.ainsert(*self.created_models)

    async def load_data(self):
        return tuple(
            [await self.real_redis_client.exists(m.key) for m in self.created_models]
        )

    def expected_before(self):
        return 0, 0

    def expected_after(self):
        return 1, 1


class TestRapyerDelete(TwoModelDeleteBase):
    covered_method = AtomicRedisModel.adelete

    async def perform_action(self, piped):
        model1, _ = self.created_models
        await model1.adelete()


class TestRapyerDeleteByKey(TwoModelDeleteBase):
    covered_method = AtomicRedisModel.adelete_by_key

    async def perform_action(self, piped):
        model1, _ = self.created_models
        await ComprehensiveTestModel.adelete_by_key(model1.key)


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
        await ComprehensiveTestModel.adelete_many(model2, model3)

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


class TestRapyerAsetTtl(ActionTestBase):
    covered_method = AtomicRedisModel.aset_ttl

    def create_models(self):
        return [
            UserModelWithoutTTL(name="user1", age=25),
            UserModelWithoutTTL(name="user2", age=30),
            UserModelWithoutTTL(name="user3", age=35),
        ]

    async def setup_data(self):
        models = await super().setup_data()
        ttls_before = [await self.real_redis_client.ttl(m.key) for m in models]
        assert all(ttl == -1 for ttl in ttls_before)
        return models

    async def perform_action(self, piped):
        for m in self.created_models:
            await m.aset_ttl(TTL_SECONDS)

    async def load_data(self):
        return [await self.real_redis_client.ttl(m.key) for m in self.created_models]

    def expected_before(self):
        return [-1, -1, -1]

    def assert_after_pipeline(self, loaded):
        assert all(0 < ttl <= TTL_SECONDS for ttl in loaded), loaded


class TestRedisIntAincrease(AsyncComprehensiveCounterOpBase):
    covered_method = RedisInt.aincrease

    def create_models(self):
        return [ComprehensiveTestModel(counter=10)]

    async def perform_action(self, piped: ComprehensiveTestModel) -> None:
        await piped.counter.aincrease(5)

    def expected_before(self):
        return 10

    def expected_after(self):
        return 15


class TestRedisListInsert(ComprehensiveTagsOpBase):
    covered_method = RedisList.insert

    def create_models(self):
        return [ComprehensiveTestModel(tags=["first", "last"])]

    async def perform_action(self, piped):
        piped.tags.insert(1, "middle")

    def expected_before(self):
        return ["first", "last"]

    def expected_after(self):
        return ["first", "middle", "last"]


class TestRedisListClear(ComprehensiveTagsOpBase):
    covered_method = RedisList.clear

    def create_models(self):
        return [ComprehensiveTestModel(tags=["tag1", "tag2", "tag3"])]

    async def perform_action(self, piped):
        piped.tags.clear()

    def expected_before(self):
        return ["tag1", "tag2", "tag3"]

    def expected_after(self):
        return []


class TestRedisListRemoveRange(ComprehensiveTagsOpBase):
    covered_method = RedisList.remove_range

    def create_models(self):
        return [ComprehensiveTestModel(tags=["a", "b", "c", "d", "e"])]

    async def perform_action(self, piped):
        piped.tags.remove_range(1, 3)

    def expected_before(self):
        return ["a", "b", "c", "d", "e"]

    def expected_after(self):
        return ["a", "d", "e"]


class TestRedisDictClear(ComprehensiveMetadataOpBase):
    covered_method = RedisDict.clear

    def create_models(self):
        return [ComprehensiveTestModel(metadata={"key1": "val1", "key2": "val2"})]

    async def perform_action(self, piped):
        piped.metadata.clear()

    def expected_before(self):
        return {"key1": "val1", "key2": "val2"}

    def expected_after(self):
        return {}


class TestRapyerAduplicate(ActionTestBase):
    covered_method = AtomicRedisModel.aduplicate

    duplicate: ComprehensiveTestModel | None = None

    def create_models(self):
        return [ComprehensiveTestModel(name="original", counter=42, tags=["t1"])]

    async def perform_action(self, piped):
        self.duplicate = await self.created_models[0].aduplicate()

    async def load_data(self):
        exists = await self.real_redis_client.exists(self.duplicate.key)
        if not exists:
            return 0, None, None, None
        loaded = await ComprehensiveTestModel.aget(self.duplicate.key)
        return 1, loaded.name, loaded.counter, loaded.tags

    def expected_before(self):
        return 0, None, None, None

    def expected_after(self):
        return 1, "original", 42, ["t1"]

    def assert_after_pipeline(self, loaded):
        super().assert_after_pipeline(loaded)
        assert self.duplicate.pk != self.created_models[0].pk


class TestRapyerAduplicateMany(ActionTestBase):
    covered_method = AtomicRedisModel.aduplicate_many

    duplicates: list[ComprehensiveTestModel] | None = None

    def create_models(self):
        return [ComprehensiveTestModel(name="original", counter=42, tags=["t1"])]

    async def perform_action(self, piped):
        self.duplicates = await self.created_models[0].aduplicate_many(3)

    async def load_data(self):
        results = []
        for dup in self.duplicates:
            exists = await self.real_redis_client.exists(dup.key)
            if not exists:
                results.append((0, None, None, None))
                continue
            loaded = await ComprehensiveTestModel.aget(dup.key)
            results.append((1, loaded.name, loaded.counter, loaded.tags))
        return results

    def expected_before(self):
        return [(0, None, None, None)] * 3

    def expected_after(self):
        return [(1, "original", 42, ["t1"])] * 3

    def assert_after_pipeline(self, loaded):
        super().assert_after_pipeline(loaded)
        all_pks = [self.created_models[0].pk] + [d.pk for d in self.duplicates]
        assert len(set(all_pks)) == 4


class TestRapyerAupdate(UpdateActionTestBase, AsyncActionTestBase):
    """After aupdate was switched to ``ensure_pipeline``, it defers to an outer
    pipeline like every other mutation."""

    covered_method = AtomicRedisModel.aupdate

    def create_models(self):
        return [ComprehensiveTestModel(name="original", counter=10)]

    async def perform_action(self, piped: ComprehensiveTestModel) -> None:
        await self.created_models[0].aupdate(name="updated", counter=99)

    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.created_models[0].key)
        return loaded.name, loaded.counter

    def expected_before(self):
        return "original", 10

    def expected_after(self):
        return "updated", 99


class TestRapyerRefreshTtl(ActionTestBase):
    covered_method = AtomicRedisModel.refresh_ttl_if_needed
    reduced_ttl: int = 10

    def create_models(self):
        return [TTLRefreshTestModel(name="ttl_test", age=25)]

    async def setup_data(self):
        models = await super().setup_data()
        model = models[0]
        # Lower the TTL so there's a measurable gap to refresh.
        await self.real_redis_client.expire(model.key, self.reduced_ttl)
        ttl_before = await self.real_redis_client.ttl(model.key)
        assert 0 < ttl_before <= self.reduced_ttl
        return models

    async def perform_action(self, piped):
        await self.created_models[0].refresh_ttl_if_needed(can_use_pipeline=True)

    async def load_data(self):
        return await self.real_redis_client.ttl(self.created_models[0].key)

    def assert_during_pipeline(self, loaded):
        assert loaded <= self.reduced_ttl

    def assert_after_pipeline(self, loaded):
        assert self.reduced_ttl < loaded <= TTL_TEST_SECONDS
