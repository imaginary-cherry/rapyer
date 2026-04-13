import pytest

import rapyer
from rapyer.base import AtomicRedisModel
from rapyer.types.dct import RedisDict
from rapyer.types.integer import RedisInt
from rapyer.types.lst import RedisList
from tests.conftest import standalone_pipeline_test_for
from tests.integration.pipeline.pipeline_atomicity_base import (
    ComprehensiveMetadataOpBase,
    ComprehensiveTagsOpBase,
    PipelineAtomicityBase,
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


# The standalone-pipeline ainsert test isn't in scope — kept as a plain function.
@standalone_pipeline_test_for(AtomicRedisModel.ainsert)
@pytest.mark.asyncio
async def test_pipeline_model_ainsert__standalone_pipeline__check_atomicity(
    real_redis_client,
):
    # Arrange
    model1 = ComprehensiveTestModel(name="model1")
    model2 = ComprehensiveTestModel(name="model2")

    # Act
    async with rapyer.apipeline():
        await ComprehensiveTestModel.ainsert(model1, model2)

        # Assert - models not visible during pipeline
        exists1 = await real_redis_client.exists(model1.key)
        exists2 = await real_redis_client.exists(model2.key)
        assert exists1 == 0
        assert exists2 == 0

    # Assert - models exist after pipeline
    loaded1 = await ComprehensiveTestModel.aget(model1.key)
    loaded2 = await ComprehensiveTestModel.aget(model2.key)
    assert loaded1.name == "model1"
    assert loaded2.name == "model2"


@standalone_pipeline_test_for(AtomicRedisModel.adelete)
@pytest.mark.asyncio
async def test_pipeline_model_adelete__standalone_pipeline__check_atomicity(
    real_redis_client,
):
    # Arrange
    model = ComprehensiveTestModel(name="to_delete")
    await model.asave()

    # Act
    async with rapyer.apipeline():
        await model.adelete()

        # Assert - model still exists during pipeline
        exists = await real_redis_client.exists(model.key)
        assert exists == 1

    # Assert - model deleted after pipeline
    exists = await real_redis_client.exists(model.key)
    assert exists == 0


@standalone_pipeline_test_for(AtomicRedisModel.adelete_by_key)
@pytest.mark.asyncio
async def test_pipeline_model_adelete_by_key__standalone_pipeline__check_atomicity(
    real_redis_client,
):
    # Arrange
    model = ComprehensiveTestModel(name="to_delete")
    await model.asave()

    # Act
    async with rapyer.apipeline():
        await ComprehensiveTestModel.adelete_by_key(model.key)

        # Assert - model still exists during pipeline
        exists = await real_redis_client.exists(model.key)
        assert exists == 1

    # Assert - model deleted after pipeline
    exists = await real_redis_client.exists(model.key)
    assert exists == 0


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


@standalone_pipeline_test_for(AtomicRedisModel.aset_ttl)
@pytest.mark.asyncio
async def test_pipeline_model_aset_ttl__standalone_pipeline__check_atomicity(
    real_redis_client,
):
    # Arrange
    model = UserModelWithoutTTL(name="user1", age=25)
    await model.asave()
    assert await real_redis_client.ttl(model.key) == -1

    # Act
    async with rapyer.apipeline():
        await model.aset_ttl(TTL_SECONDS)

        # Assert - TTL not set during pipeline
        ttl_during = await real_redis_client.ttl(model.key)
        assert ttl_during == -1

    # Assert - TTL set after pipeline
    ttl_after = await real_redis_client.ttl(model.key)
    assert 0 < ttl_after <= TTL_SECONDS


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


@standalone_pipeline_test_for(AtomicRedisModel.aduplicate)
@pytest.mark.asyncio
async def test_pipeline_model_aduplicate__standalone_pipeline__check_atomicity():
    # Arrange
    model = ComprehensiveTestModel(name="original", counter=42, tags=["t1"])
    await model.asave()

    # Act
    async with rapyer.apipeline():
        duplicate = await model.aduplicate()

        # Assert - duplicate not visible during pipeline
        assert not await ComprehensiveTestModel.aexists(duplicate.key)

    # Assert - duplicate exists after pipeline with correct values
    loaded = await ComprehensiveTestModel.aget(duplicate.key)
    assert loaded.name == "original"
    assert loaded.counter == 42
    assert loaded.tags == ["t1"]
    assert duplicate.pk != model.pk


@standalone_pipeline_test_for(AtomicRedisModel.aduplicate_many)
@pytest.mark.asyncio
async def test_pipeline_model_aduplicate_many__standalone_pipeline__check_atomicity():
    # Arrange
    model = ComprehensiveTestModel(name="original", counter=42, tags=["t1"])
    await model.asave()

    # Act
    async with rapyer.apipeline():
        duplicates = await model.aduplicate_many(3)

        # Assert - duplicates not visible during pipeline
        for dup in duplicates:
            assert not await ComprehensiveTestModel.aexists(dup.key)

    # Assert - all duplicates exist after pipeline
    for dup in duplicates:
        loaded = await ComprehensiveTestModel.aget(dup.key)
        assert loaded.name == "original"
        assert loaded.counter == 42
        assert loaded.tags == ["t1"]

    # All PKs should be unique
    all_pks = [model.pk] + [d.pk for d in duplicates]
    assert len(set(all_pks)) == 4


@standalone_pipeline_test_for(AtomicRedisModel.aupdate)
@pytest.mark.asyncio
async def test_pipeline_model_aupdate__standalone_pipeline__executes_immediately():
    # Arrange
    model = ComprehensiveTestModel(name="original", counter=10)
    await model.asave()

    # Act - aupdate uses its own internal pipeline, so changes are
    # visible immediately even inside an outer pipeline context
    async with rapyer.apipeline():
        await model.aupdate(name="updated", counter=99)

        # Assert - changes visible during pipeline (aupdate is self-contained)
        loaded = await ComprehensiveTestModel.aget(model.key)
        assert loaded.name == "updated"
        assert loaded.counter == 99

    # Assert - still correct after outer pipeline exits
    final = await ComprehensiveTestModel.aget(model.key)
    assert final.name == "updated"
    assert final.counter == 99


@standalone_pipeline_test_for(AtomicRedisModel.refresh_ttl_if_needed)
@pytest.mark.asyncio
async def test_pipeline_model_refresh_ttl__standalone_pipeline__check_atomicity(
    real_redis_client,
):
    # Arrange
    model = TTLRefreshTestModel(name="ttl_test", age=25)
    await model.asave()
    # Reduce TTL to create a measurable gap
    reduced_ttl = 10
    await real_redis_client.expire(model.key, reduced_ttl)
    ttl_before = await real_redis_client.ttl(model.key)
    assert 0 < ttl_before <= reduced_ttl

    # Act
    async with rapyer.apipeline():
        await model.refresh_ttl_if_needed(can_use_pipeline=True)

        # Assert - TTL not refreshed during pipeline
        ttl_during = await real_redis_client.ttl(model.key)
        assert ttl_during <= reduced_ttl

    # Assert - TTL refreshed after pipeline
    ttl_after = await real_redis_client.ttl(model.key)
    assert ttl_after > reduced_ttl
    assert ttl_after <= TTL_TEST_SECONDS
