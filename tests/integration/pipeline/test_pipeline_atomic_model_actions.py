import rapyer
from rapyer.base import AtomicRedisModel
from rapyer.types.dct import RedisDict
from rapyer.types.integer import RedisInt
from rapyer.types.lst import RedisList
from tests.integration.pipeline.pipeline_atomicity_base import (
    ComprehensiveMetadataOpBase,
    ComprehensiveTagsOpBase,
    PipelineAtomicityBase,
    RapyerPipelineBase,
    TwoModelDeleteBase,
)
from tests.models.collection_types import ComprehensiveTestModel
from tests.models.simple_types import (
    TTL_TEST_SECONDS,
    TTLRefreshTestModel,
    UserModelWithoutTTL,
)

TTL_SECONDS = 300


class TestPipelineModelAsave(PipelineAtomicityBase):
    covered_method = AtomicRedisModel.asave

    def create_models(self):
        return ComprehensiveTestModel(name="original", counter=10)

    async def perform_action(self, piped):
        piped.name = "updated"
        piped.counter = 99
        await piped.asave()

    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.handle.key)
        return loaded.name, loaded.counter

    def expected_before(self):
        return "original", 10

    def expected_after(self):
        return "updated", 99


class TestPipelineModelAinsert(PipelineAtomicityBase):
    """Verify ``ainsert`` inside a model pipeline defers the new model's creation."""

    covered_method = AtomicRedisModel.ainsert

    def create_models(self):
        # Only the existing model is inserted; the new model is the test subject.
        return ComprehensiveTestModel(name="existing")

    async def setup_data(self):
        existing_model = await super().setup_data()
        new_model = ComprehensiveTestModel(name="inserted")
        return existing_model, new_model

    def pipeline_owner(self):
        existing, _new = self.handle
        return existing

    async def perform_action(self, piped):
        _existing, new_model = self.handle
        await ComprehensiveTestModel.ainsert(new_model)

    async def load_data(self):
        """Return ``(exists_flag, name_or_None)`` for the new model."""
        _existing, new_model = self.handle
        exists = await self.real_redis_client.exists(new_model.key)
        if not exists:
            return 0, None
        loaded = await ComprehensiveTestModel.aget(new_model.key)
        return 1, loaded.name

    def expected_before(self):
        return 0, None

    def expected_after(self):
        return 1, "inserted"


# NOTE: mirrors TestPipelineModelAinsert but exercises the module-level
# ``rapyer.apipeline()`` context instead of the instance pipeline.
class TestRapyerPipelineAinsert(RapyerPipelineBase):
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
        await ComprehensiveTestModel.ainsert(*self.handle)

    async def load_data(self):
        return tuple([await self.real_redis_client.exists(m.key) for m in self.handle])

    def expected_before(self):
        return 0, 0

    def expected_after(self):
        return 1, 1


# NOTE: mirrors TestPipelineDelete but exercises the module-level
# ``rapyer.apipeline()`` context instead of the instance pipeline.
class TestRapyerPipelineDelete(TwoModelDeleteBase):
    covered_method = AtomicRedisModel.adelete

    def pipeline_owner(self):
        return rapyer

    async def perform_action(self, piped):
        model1, _ = self.handle
        await model1.adelete()


# NOTE: mirrors TestPipelineTryDelete but exercises the module-level
# ``rapyer.apipeline()`` context instead of the instance pipeline.
class TestRapyerPipelineDeleteByKey(TwoModelDeleteBase):
    covered_method = AtomicRedisModel.adelete_by_key

    def pipeline_owner(self):
        return rapyer

    async def perform_action(self, piped):
        model1, _ = self.handle
        await ComprehensiveTestModel.adelete_by_key(model1.key)


class TestPipelineModelAdeleteMany(PipelineAtomicityBase):
    covered_method = AtomicRedisModel.adelete_many

    def create_models(self):
        return [
            ComprehensiveTestModel(name="model1"),
            ComprehensiveTestModel(name="model2"),
            ComprehensiveTestModel(name="model3"),
        ]

    def pipeline_owner(self):
        return self.handle[0]

    async def perform_action(self, piped):
        _model1, model2, model3 = self.handle
        await ComprehensiveTestModel.adelete_many(model2, model3)

    async def load_data(self):
        _model1, model2, model3 = self.handle
        return (
            await self.real_redis_client.exists(model2.key),
            await self.real_redis_client.exists(model3.key),
        )

    def expected_before(self):
        return 1, 1

    def expected_after(self):
        return 0, 0


# NOTE: mirrors TestPipelineAsetTtl but exercises the module-level
# ``rapyer.apipeline()`` context instead of the instance pipeline.
class TestRapyerPipelineAsetTtl(RapyerPipelineBase):
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
        for m in self.handle:
            await m.aset_ttl(TTL_SECONDS)

    async def load_data(self):
        return [await self.real_redis_client.ttl(m.key) for m in self.handle]

    def expected_before(self):
        return [-1, -1, -1]

    def assert_after_pipeline(self, loaded):
        assert all(0 < ttl <= TTL_SECONDS for ttl in loaded), loaded

    def expected_after(self):
        # Unused — ``assert_after_pipeline`` does a range check instead.
        return None


class TestPipelineRedisIntAincrease(PipelineAtomicityBase):
    covered_method = RedisInt.aincrease

    def create_models(self):
        return ComprehensiveTestModel(counter=10)

    async def perform_action(self, piped):
        await piped.counter.aincrease(5)

    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.handle.key)
        return loaded.counter

    def expected_before(self):
        return 10

    def expected_after(self):
        return 15


class TestPipelineRedisListInsert(ComprehensiveTagsOpBase):
    covered_method = RedisList.insert

    def create_models(self):
        return ComprehensiveTestModel(tags=["first", "last"])

    async def perform_action(self, piped):
        piped.tags.insert(1, "middle")

    def expected_before(self):
        return ["first", "last"]

    def expected_after(self):
        return ["first", "middle", "last"]


class TestPipelineRedisListClear(ComprehensiveTagsOpBase):
    covered_method = RedisList.clear

    def create_models(self):
        return ComprehensiveTestModel(tags=["tag1", "tag2", "tag3"])

    async def perform_action(self, piped):
        piped.tags.clear()

    def expected_before(self):
        return ["tag1", "tag2", "tag3"]

    def expected_after(self):
        return []


class TestPipelineRedisListRemoveRange(ComprehensiveTagsOpBase):
    covered_method = RedisList.remove_range

    def create_models(self):
        return ComprehensiveTestModel(tags=["a", "b", "c", "d", "e"])

    async def perform_action(self, piped):
        piped.tags.remove_range(1, 3)

    def expected_before(self):
        return ["a", "b", "c", "d", "e"]

    def expected_after(self):
        return ["a", "d", "e"]


class TestPipelineRedisDictClear(ComprehensiveMetadataOpBase):
    covered_method = RedisDict.clear

    def create_models(self):
        return ComprehensiveTestModel(metadata={"key1": "val1", "key2": "val2"})

    async def perform_action(self, piped):
        piped.metadata.clear()

    def expected_before(self):
        return {"key1": "val1", "key2": "val2"}

    def expected_after(self):
        return {}


class TestRapyerPipelineAduplicate(RapyerPipelineBase):
    covered_method = AtomicRedisModel.aduplicate

    duplicate: ComprehensiveTestModel | None = None

    def create_models(self):
        return ComprehensiveTestModel(name="original", counter=42, tags=["t1"])

    async def perform_action(self, piped):
        self.duplicate = await self.handle.aduplicate()

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
        assert self.duplicate.pk != self.handle.pk


class TestRapyerPipelineAduplicateMany(RapyerPipelineBase):
    covered_method = AtomicRedisModel.aduplicate_many

    duplicates: list[ComprehensiveTestModel] | None = None

    def create_models(self):
        return ComprehensiveTestModel(name="original", counter=42, tags=["t1"])

    async def perform_action(self, piped):
        self.duplicates = await self.handle.aduplicate_many(3)

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
        all_pks = [self.handle.pk] + [d.pk for d in self.duplicates]
        assert len(set(all_pks)) == 4


class TestRapyerPipelineAupdate(RapyerPipelineBase):
    """After aupdate was switched to ``ensure_pipeline``, it defers to an outer
    pipeline like every other mutation."""

    covered_method = AtomicRedisModel.aupdate

    def create_models(self):
        return ComprehensiveTestModel(name="original", counter=10)

    async def perform_action(self, piped):
        await self.handle.aupdate(name="updated", counter=99)

    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.handle.key)
        return loaded.name, loaded.counter

    def expected_before(self):
        return "original", 10

    def expected_after(self):
        return "updated", 99


class TestRapyerPipelineRefreshTtl(RapyerPipelineBase):
    covered_method = AtomicRedisModel.refresh_ttl_if_needed
    reduced_ttl: int = 10

    def create_models(self):
        return TTLRefreshTestModel(name="ttl_test", age=25)

    async def setup_data(self):
        model = await super().setup_data()
        # Lower the TTL so there's a measurable gap to refresh.
        await self.real_redis_client.expire(model.key, self.reduced_ttl)
        ttl_before = await self.real_redis_client.ttl(model.key)
        assert 0 < ttl_before <= self.reduced_ttl
        return model

    async def perform_action(self, piped):
        await self.handle.refresh_ttl_if_needed(can_use_pipeline=True)

    async def load_data(self):
        return await self.real_redis_client.ttl(self.handle.key)

    def assert_during_pipeline(self, loaded):
        assert loaded <= self.reduced_ttl

    def assert_after_pipeline(self, loaded):
        assert self.reduced_ttl < loaded <= TTL_TEST_SECONDS

    def expected_before(self):
        return None

    def expected_after(self):
        return None
