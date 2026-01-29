import pytest

from tests.models.collection_types import PipelineTestModel, ComprehensiveTestModel


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

    from rapyer.context import _context_var

    # Act & Assert - Context should be None before a pipeline
    assert _context_var.get() is None

    async with model.apipeline() as redis_model:
        # Context should be set to pipeline inside context
        assert _context_var.get() is not None
        await redis_model.metadata.aupdate(updated="true")

    # Context should be cleared after a pipeline
    assert _context_var.get() is None

    # Verify operation was executed
    final_model = await PipelineTestModel.aget(model.key)
    assert final_model.metadata == {"test": "value", "updated": "true"}


@pytest.mark.asyncio
async def test_pipeline_list_aappend__check_atomicity_sanity():
    # Arrange
    model = ComprehensiveTestModel(tags=["initial"])
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        await redis_model.tags.aappend("new_tag")

        # Check if the change is not applied yet (atomicity test)
        loaded_model = await ComprehensiveTestModel.aget(model.key)
        assert loaded_model.tags == ["initial"]

    # Assert - Check if a change was applied after a pipeline
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.tags == ["initial", "new_tag"]


@pytest.mark.asyncio
async def test_pipeline_list_aextend__check_atomicity_sanity():
    # Arrange
    model = ComprehensiveTestModel(tags=["initial"])
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        await redis_model.tags.aextend(["tag1", "tag2"])

        # Check if the change is not applied yet (atomicity test)
        loaded_model = await ComprehensiveTestModel.aget(model.key)
        assert loaded_model.tags == ["initial"]

    # Assert - Check if a change was applied after a pipeline
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.tags == ["initial", "tag1", "tag2"]


@pytest.mark.asyncio
async def test_pipeline_list_ainsert__check_atomicity_sanity():
    # Arrange
    model = ComprehensiveTestModel(tags=["first", "last"])
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        await redis_model.tags.ainsert(1, "middle")

        # Check if the change is not applied yet (atomicity test)
        loaded_model = await ComprehensiveTestModel.aget(model.key)
        assert loaded_model.tags == ["first", "last"]

    # Assert - Check if a change was applied after a pipeline
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.tags == ["first", "middle", "last"]


@pytest.mark.asyncio
async def test_pipeline_list_aclear__check_atomicity_sanity():
    # Arrange
    model = ComprehensiveTestModel(tags=["tag1", "tag2"])
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        await redis_model.tags.aclear()

        # Check if the change is not applied yet (atomicity test)
        loaded_model = await ComprehensiveTestModel.aget(model.key)
        assert loaded_model.tags == ["tag1", "tag2"]

    # Assert - Check if change was applied after pipeline
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.tags == []


@pytest.mark.asyncio
async def test_pipeline_dict_aset_item__check_atomicity_sanity():
    # Arrange
    model = ComprehensiveTestModel(metadata={"existing": "value"})
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        await redis_model.metadata.aset_item("new_key", "new_value")

        # Check if the change is not applied yet (atomicity test)
        loaded_model = await ComprehensiveTestModel.aget(model.key)
        assert loaded_model.metadata == {"existing": "value"}

    # Assert - Check if change was applied after pipeline
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.metadata == {"existing": "value", "new_key": "new_value"}


@pytest.mark.asyncio
async def test_pipeline_dict_adel_item__check_atomicity_sanity():
    # Arrange
    model = ComprehensiveTestModel(metadata={"key1": "value1", "key2": "value2"})
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        await redis_model.metadata.adel_item("key1")

        # Check if the change is not applied yet (atomicity test)
        loaded_model = await ComprehensiveTestModel.aget(model.key)
        assert loaded_model.metadata == {"key1": "value1", "key2": "value2"}

    # Assert - Check if a change was applied after a pipeline
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.metadata == {"key2": "value2"}


@pytest.mark.asyncio
async def test_pipeline_dict_aupdate__check_atomicity_sanity():
    # Arrange
    model = ComprehensiveTestModel(metadata={"existing": "value"})
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        await redis_model.metadata.aupdate(key1="value1", key2="value2")

        # Check if the change is not applied yet (atomicity test)
        loaded_model = await ComprehensiveTestModel.aget(model.key)
        assert loaded_model.metadata == {"existing": "value"}

    # Assert - Check if a change was applied after a pipeline
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.metadata == {
        "existing": "value",
        "key1": "value1",
        "key2": "value2",
    }


@pytest.mark.asyncio
async def test_pipeline_dict_aclear__check_atomicity_sanity():
    # Arrange
    model = ComprehensiveTestModel(metadata={"key1": "value1", "key2": "value2"})
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        await redis_model.metadata.aclear()

        # Check if the change is not applied yet (atomicity test)
        loaded_model = await ComprehensiveTestModel.aget(model.key)
        assert loaded_model.metadata == {"key1": "value1", "key2": "value2"}

    # Assert - Check if a change was applied after pipeline
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.metadata == {}


@pytest.mark.asyncio
async def test_pipeline_string_set__check_atomicity_sanity():
    # Arrange
    model = ComprehensiveTestModel(name="original")
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.name = "updated"
        await redis_model.name.asave()

        # Check if the change is not applied yet (atomicity test)
        loaded_model = await ComprehensiveTestModel.aget(model.key)
        assert loaded_model.name == "original"

    # Assert - Check if a change was applied after a pipeline
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.name == "updated"


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


@pytest.mark.asyncio
async def test_pipeline_delete__check_atomicity_sanity(real_redis_client):
    # Arrange
    model1 = ComprehensiveTestModel(tags=["tag1"], name="model1")
    model2 = ComprehensiveTestModel(tags=["tag2"], name="model2")
    await model1.asave()
    await model2.asave()

    # Act
    async with model1.apipeline() as redis_model:
        await redis_model.adelete()

        # Check if models still exist during a pipeline (atomicity test)
        key1_exists = await real_redis_client.exists(model1.key)
        key2_exists = await real_redis_client.exists(model2.key)
        assert key1_exists == 1
        assert key2_exists == 1

    # Assert - Check if model1 was deleted after a pipeline
    key1_exists = await real_redis_client.exists(model1.key)
    key2_exists = await real_redis_client.exists(model2.key)
    assert key1_exists == 0
    assert key2_exists == 1


@pytest.mark.asyncio
async def test_pipeline_try_delete__check_atomicity_sanity(real_redis_client):
    # Arrange
    model1 = ComprehensiveTestModel(tags=["tag1"], name="model1")
    model2 = ComprehensiveTestModel(tags=["tag2"], name="model2")
    await model1.asave()
    await model2.asave()

    # Act
    async with model1.apipeline() as redis_model:
        await ComprehensiveTestModel.adelete_by_key(model1.key)

        # Check if models still exist during pipeline (atomicity test)
        key1_exists = await real_redis_client.exists(model1.key)
        key2_exists = await real_redis_client.exists(model2.key)
        assert key1_exists == 1
        assert key2_exists == 1

    # Assert - Check if model1 was deleted after pipeline and result was True
    key1_exists = await real_redis_client.exists(model1.key)
    key2_exists = await real_redis_client.exists(model2.key)
    assert key1_exists == 0
    assert key2_exists == 1


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
