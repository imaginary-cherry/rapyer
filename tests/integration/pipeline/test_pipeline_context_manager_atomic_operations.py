import pytest

from rapyer.base import AtomicRedisModel
from rapyer.context import _context_pipe
from rapyer.types.base import RedisType
from rapyer.types.dct import RedisDict
from rapyer.types.lst import RedisList
from tests.integration.pipeline.pipeline_atomicity_base import (
    AsyncActionTestBase,
    AsyncComprehensiveMetadataOpBase,
    AsyncComprehensiveTagsOpBase,
    TwoModelDeleteBase,
)
from tests.models.collection_types import (
    ComprehensiveTestModel,
    NoRefreshTTLComprehensiveTestModel,
    PipelineTestModel,
    TTLComprehensiveTestModel,
)


@pytest.mark.asyncio
async def test_pipeline_context_manager__dict_update_operations__check_atomic_batch_sanity():
    # Arrange
    original_metadata = {"original": "value"}
    expected_metadata = {
        "original": "value",
        "key1": "value1",
        "key2": "value2",
        "key3": "value3",
        "key4": "value4",
    }
    model = PipelineTestModel(metadata=original_metadata)
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.metadata.update(key1="value1", key2="value2")
        await redis_model.metadata.aupdate(key3="value3", key4="value4")

        # Check that none of the operations have been applied to Redis yet
        loaded_model = await PipelineTestModel.aget(model.key)
        assert loaded_model.metadata == original_metadata

    # Assert - All dict operations should be applied atomically
    final_model = await PipelineTestModel.aget(model.key)
    assert final_model.metadata == expected_metadata


@pytest.mark.asyncio
async def test_pipeline_context_manager__multiple_dict_fields__check_atomic_execution_sanity():
    # Arrange
    model = PipelineTestModel(metadata={"env": "dev"}, config={"port": 8080})
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        await redis_model.metadata.aupdate(status="active", version="1.0")
        await redis_model.config.aupdate(timeout=30, retries=3)

        # Check that none of the operations have been applied to Redis yet
        loaded_model_1 = await PipelineTestModel.aget(model.key)
        assert loaded_model_1.metadata == {"env": "dev"}

        await redis_model.metadata.aupdate(region="us-east")

        # Check again that changes still haven't been applied
        loaded_model_2 = await PipelineTestModel.aget(model.key)
        assert loaded_model_2.metadata == {"env": "dev"}
        assert loaded_model_2.config == {"port": 8080}

    # Assert - All changes should be applied atomically
    final_model = await PipelineTestModel.aget(model.key)
    assert final_model.metadata == {
        "env": "dev",
        "status": "active",
        "version": "1.0",
        "region": "us-east",
    }
    assert final_model.config == {"port": 8080, "timeout": 30, "retries": 3}


@pytest.mark.asyncio
async def test_pipeline_context_manager__exception_during_pipeline__check_no_changes_applied_edge_case():
    # Arrange
    model = PipelineTestModel(metadata={"key": "original"})
    await model.asave()
    original_data = await PipelineTestModel.aget(model.key)

    # Act & Assert
    with pytest.raises(ValueError, match="Test exception"):
        async with model.apipeline() as redis_model:
            await redis_model.metadata.aupdate(should_not_be_saved="value")
            raise ValueError("Test exception")

    # Assert - No changes should be applied when an exception occurs
    final_model = await PipelineTestModel.aget(model.key)
    assert final_model.metadata == original_data.metadata


@pytest.mark.asyncio
async def test_pipeline_context_manager__empty_pipeline__check_no_operations_edge_case():
    # Arrange
    model = PipelineTestModel(metadata={"key": "unchanged"})
    await model.asave()
    original_data = await PipelineTestModel.aget(model.key)

    # Act
    async with model.apipeline() as redis_model:
        pass  # No operations

    # Assert - Data should remain unchanged
    final_model = await PipelineTestModel.aget(model.key)
    assert final_model.metadata == original_data.metadata


@pytest.mark.asyncio
async def test_pipeline_context_manager__incremental_updates_atomic__check_intermediate_state_sanity():
    # Arrange
    model = PipelineTestModel(metadata={"stage": "init"}, config={"step": 0})
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        # First update
        await redis_model.metadata.aupdate(stage="processing", started_at="2023-01-01")

        # Check Redis state - should still be original
        loaded_model_1 = await PipelineTestModel.aget(model.key)
        assert loaded_model_1.metadata == {"stage": "init"}
        assert loaded_model_1.config == {"step": 0}

        # Second update
        await redis_model.config.aupdate(step=1, timeout=30)

        # Check Redis state again - should still be original
        loaded_model_2 = await PipelineTestModel.aget(model.key)
        assert loaded_model_2.metadata == {"stage": "init"}
        assert loaded_model_2.config == {"step": 0}

        # Third update
        await redis_model.metadata.aupdate(stage="completed")

    # Assert - All updates should be applied atomically
    final_model = await PipelineTestModel.aget(model.key)
    assert final_model.metadata == {"stage": "completed", "started_at": "2023-01-01"}
    assert final_model.config == {"step": 1, "timeout": 30}


@pytest.mark.asyncio
async def test_pipeline_context_manager__pipeline_context_cleanup__check_context_variable_sanity():
    # Arrange
    model = PipelineTestModel(metadata={"test": "value"})
    await model.asave()

    # Act & Assert - Context should be None before a pipeline
    assert _context_pipe.get() is None

    async with model.apipeline() as redis_model:
        # Context should be set to pipeline inside context
        assert _context_pipe.get() is not None
        await redis_model.metadata.aupdate(updated="true")

    # Context should be cleared after a pipeline
    assert _context_pipe.get() is None

    # Verify operation was executed
    final_model = await PipelineTestModel.aget(model.key)
    assert final_model.metadata == {"test": "value", "updated": "true"}


# =============================================================================
# RedisList atomicity tests
# =============================================================================


class TestPipelineListAappend(AsyncComprehensiveTagsOpBase):
    covered_method = RedisList.aappend

    def create_models(self):
        return [ComprehensiveTestModel(tags=["initial"])]

    async def perform_action(self, piped: ComprehensiveTestModel):
        await piped.tags.aappend("new_tag")

    def expected_before(self):
        return ["initial"]

    def expected_after(self):
        return ["initial", "new_tag"]


class TestPipelineListAextend(AsyncComprehensiveTagsOpBase):
    covered_method = RedisList.aextend

    def create_models(self):
        return [ComprehensiveTestModel(tags=["initial"])]

    async def perform_action(self, piped: ComprehensiveTestModel):
        await piped.tags.aextend(["tag1", "tag2"])

    def expected_before(self):
        return ["initial"]

    def expected_after(self):
        return ["initial", "tag1", "tag2"]


class TestPipelineListAinsert(AsyncComprehensiveTagsOpBase):
    covered_method = RedisList.ainsert

    def create_models(self):
        return [ComprehensiveTestModel(tags=["first", "last"])]

    async def perform_action(self, piped: ComprehensiveTestModel):
        await piped.tags.ainsert(1, "middle")

    def expected_before(self):
        return ["first", "last"]

    def expected_after(self):
        return ["first", "middle", "last"]


class TestPipelineListAclear(AsyncComprehensiveTagsOpBase):
    covered_method = RedisList.aclear

    def create_models(self):
        return [ComprehensiveTestModel(tags=["tag1", "tag2"])]

    async def perform_action(self, piped: ComprehensiveTestModel):
        await piped.tags.aclear()

    def expected_before(self):
        return ["tag1", "tag2"]

    def expected_after(self):
        return []


class TestListApop(AsyncComprehensiveTagsOpBase):
    covered_method = RedisList.apop

    def create_models(self):
        return [ComprehensiveTestModel(tags=["tag1", "tag2"])]

    async def perform_action(self, piped: ComprehensiveTestModel):
        await piped.tags.apop()

    def expected_before(self):
        return ["tag1", "tag2"]

    def expected_after(self):
        return ["tag1"]

    @pytest.mark.asyncio
    async def test_pipeline_atomicity(self, test_input):
        pytest.skip("RedisList.apop returns a value; cannot be deferred in a pipeline")


# =============================================================================
# RedisDict atomicity tests
# =============================================================================


class TestPipelineDictAsetItem(AsyncComprehensiveMetadataOpBase):
    covered_method = RedisDict.aset_item

    def create_models(self):
        return [ComprehensiveTestModel(metadata={"existing": "value"})]

    async def perform_action(self, piped: ComprehensiveTestModel):
        await piped.metadata.aset_item("new_key", "new_value")

    def expected_before(self):
        return {"existing": "value"}

    def expected_after(self):
        return {"existing": "value", "new_key": "new_value"}


class TestPipelineDictAdelItem(AsyncComprehensiveMetadataOpBase):
    covered_method = RedisDict.adel_item

    def create_models(self):
        return [ComprehensiveTestModel(metadata={"key1": "value1", "key2": "value2"})]

    async def perform_action(self, piped: ComprehensiveTestModel):
        await piped.metadata.adel_item("key1")

    def expected_before(self):
        return {"key1": "value1", "key2": "value2"}

    def expected_after(self):
        return {"key2": "value2"}


class TestPipelineDictAupdate(AsyncComprehensiveMetadataOpBase):
    covered_method = RedisDict.aupdate

    def create_models(self):
        return [ComprehensiveTestModel(metadata={"existing": "value"})]

    async def perform_action(self, piped: ComprehensiveTestModel):
        await piped.metadata.aupdate(key1="value1", key2="value2")

    def expected_before(self):
        return {"existing": "value"}

    def expected_after(self):
        return {
            "existing": "value",
            "key1": "value1",
            "key2": "value2",
        }


class TestPipelineDictAclear(AsyncComprehensiveMetadataOpBase):
    covered_method = RedisDict.aclear

    def create_models(self):
        return [ComprehensiveTestModel(metadata={"key1": "value1", "key2": "value2"})]

    async def perform_action(self, piped: ComprehensiveTestModel):
        await piped.metadata.aclear()

    def expected_before(self):
        return {"key1": "value1", "key2": "value2"}

    def expected_after(self):
        return {}


class TestDictApop(AsyncComprehensiveMetadataOpBase):
    covered_method = RedisDict.apop

    def create_models(self):
        return [ComprehensiveTestModel(metadata={"key1": "value1", "key2": "value2"})]

    async def perform_action(self, piped: ComprehensiveTestModel):
        await piped.metadata.apop("key1")

    def expected_before(self):
        return {"key1": "value1", "key2": "value2"}

    def expected_after(self):
        return {"key2": "value2"}

    @pytest.mark.asyncio
    async def test_pipeline_atomicity(self, test_input):
        pytest.skip("RedisDict.apop returns a value; cannot be deferred in a pipeline")


class TestDictApopitem(AsyncComprehensiveMetadataOpBase):
    covered_method = RedisDict.apopitem

    def create_models(self):
        # Single-entry dict so the popped item is deterministic.
        return [ComprehensiveTestModel(metadata={"only": "value"})]

    async def perform_action(self, piped: ComprehensiveTestModel):
        await piped.metadata.apopitem()

    def expected_before(self):
        return {"only": "value"}

    def expected_after(self):
        return {}

    @pytest.mark.asyncio
    async def test_pipeline_atomicity(self, test_input):
        pytest.skip(
            "RedisDict.apopitem returns a value; cannot be deferred in a pipeline"
        )


# =============================================================================
# String / scalar atomicity
# =============================================================================


class TestPipelineStringSet(AsyncActionTestBase):
    covered_method = RedisType.asave
    ttl_model_cls = TTLComprehensiveTestModel
    no_refresh_ttl_model_cls = NoRefreshTTLComprehensiveTestModel

    def create_models(self):
        return [ComprehensiveTestModel(name="original")]

    async def perform_action(self, piped: ComprehensiveTestModel):
        piped.name = "updated"
        await piped.name.asave()

    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.created_models[0].key)
        return loaded.name

    def expected_before(self):
        return "original"

    def expected_after(self):
        return "updated"


@pytest.mark.asyncio
async def test_pipeline_int_set__check_atomicity_sanity():
    # Arrange
    model = ComprehensiveTestModel(counter=10)
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.counter = 99
        await redis_model.counter.asave()

        # Check if a change is not applied yet (atomicity test)
        loaded_model = await ComprehensiveTestModel.aget(model.key)
        assert loaded_model.counter == 10

    # Assert - Check if a change was applied after a pipeline
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.counter == 99


@pytest.mark.asyncio
async def test_pipeline_multiple_operations__check_combined_atomicity_sanity():
    # Arrange
    model = ComprehensiveTestModel(
        tags=["tag1"], metadata={"key1": "value1"}, name="original", counter=0
    )
    await model.asave()

    # Act - Test multiple operations in a single pipeline
    async with model.apipeline() as redis_model:
        await redis_model.tags.aappend("tag2")
        await redis_model.tags.aextend(["tag3", "tag4"])
        await redis_model.metadata.aupdate(key2="value2", key3="value3")
        await redis_model.metadata.aset_item("key4", "value4")
        redis_model.name = "updated"
        await redis_model.name.asave()
        redis_model.counter = 100
        await redis_model.counter.asave()

        # Check intermediate state - should be unchanged
        loaded_model = await ComprehensiveTestModel.aget(model.key)
        assert loaded_model.tags == ["tag1"]
        assert loaded_model.metadata == {"key1": "value1"}
        assert loaded_model.name == "original"
        assert loaded_model.counter == 0

    # Assert - All changes should be applied atomically
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.tags == ["tag1", "tag2", "tag3", "tag4"]
    assert final_model.metadata == {
        "key1": "value1",
        "key2": "value2",
        "key3": "value3",
        "key4": "value4",
    }
    assert final_model.name == "updated"
    assert final_model.counter == 100


@pytest.mark.asyncio
async def test_pipeline_exception_rollback__check_no_changes_applied_edge_case():
    # Arrange
    model = ComprehensiveTestModel(tags=["original"], metadata={"key": "original"})
    await model.asave()
    original_state = await ComprehensiveTestModel.aget(model.key)

    # Act & Assert - Pipeline should roll back on exception
    with pytest.raises(ValueError, match="Test exception"):
        async with model.apipeline() as redis_model:
            await redis_model.tags.aappend("should_not_be_saved")
            await redis_model.metadata.aset_item("new_key", "should_not_be_saved")
            raise ValueError("Test exception")

    # Assert - No changes should be applied when an exception occurs
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.tags == original_state.tags
    assert final_model.metadata == original_state.metadata


# =============================================================================
# Delete atomicity tests (use `real_redis_client.exists` rather than aget)
# =============================================================================


class TestPipelineDelete(TwoModelDeleteBase):
    covered_method = AtomicRedisModel.adelete

    async def perform_action(self, piped):
        await piped.adelete()


class TestPipelineTryDelete(TwoModelDeleteBase):
    covered_method = AtomicRedisModel.adelete_by_key

    async def perform_action(self, piped):
        model1, _model2 = self.created_models
        await ComprehensiveTestModel.adelete_by_key(model1.key)


@pytest.mark.asyncio
async def test_pipeline_multiple_deletes__check_atomicity_sanity(real_redis_client):
    # Arrange
    model1 = ComprehensiveTestModel(tags=["tag1"], name="model1")
    model2 = ComprehensiveTestModel(tags=["tag2"], name="model2")
    model3 = ComprehensiveTestModel(tags=["tag3"], name="model3")
    await model1.asave()
    await model2.asave()
    await model3.asave()

    # Act
    async with model1.apipeline() as redis_model:
        await redis_model.adelete()
        await ComprehensiveTestModel.adelete_by_key(model2.key)

        # Check if all models still exist during pipeline (atomicity test)
        key1_exists = await real_redis_client.exists(model1.key)
        key2_exists = await real_redis_client.exists(model2.key)
        key3_exists = await real_redis_client.exists(model3.key)
        assert key1_exists == 1
        assert key2_exists == 1
        assert key3_exists == 1

    # Assert - Check if model1 and model2 were deleted after pipeline, model3 remains
    key1_exists = await real_redis_client.exists(model1.key)
    key2_exists = await real_redis_client.exists(model2.key)
    key3_exists = await real_redis_client.exists(model3.key)
    assert key1_exists == 0
    assert key2_exists == 0
    assert key3_exists == 1
