import pytest

from tests.models.collection_types import ComprehensiveTestModel


@pytest.mark.asyncio
async def test_redis_list_setitem_with_pipeline_sanity():
    # Arrange
    model = ComprehensiveTestModel(tags=["first", "second", "third"])
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.tags[1] = "modified"

        # Assert - Change should not be applied yet
        loaded_model = await ComprehensiveTestModel.aget(model.key)
        assert loaded_model.tags == ["first", "second", "third"]

    # Assert - Change should be applied after pipeline
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.tags == ["first", "modified", "third"]


@pytest.mark.asyncio
async def test_redis_list_setitem_at_beginning_with_pipeline_sanity():
    # Arrange
    model = ComprehensiveTestModel(tags=["old", "middle", "last"])
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.tags[0] = "new"

        # Assert - Change should not be applied yet
        loaded_model = await ComprehensiveTestModel.aget(model.key)
        assert loaded_model.tags == ["old", "middle", "last"]

    # Assert - Change should be applied after pipeline
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.tags == ["new", "middle", "last"]


@pytest.mark.asyncio
async def test_redis_list_setitem_at_end_with_pipeline_sanity():
    # Arrange
    model = ComprehensiveTestModel(tags=["first", "middle", "old_last"])
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.tags[2] = "new_last"

        # Assert - Change should not be applied yet
        loaded_model = await ComprehensiveTestModel.aget(model.key)
        assert loaded_model.tags == ["first", "middle", "old_last"]

    # Assert - Change should be applied after pipeline
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.tags == ["first", "middle", "new_last"]


@pytest.mark.asyncio
async def test_redis_list_iadd_with_pipeline_sanity():
    # Arrange
    model = ComprehensiveTestModel(tags=["initial"])
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.tags += ["added1", "added2"]

        # Assert - Change should not be applied yet
        loaded_model = await ComprehensiveTestModel.aget(model.key)
        assert loaded_model.tags == ["initial"]

    # Assert - Change should be applied after pipeline
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.tags == ["initial", "added1", "added2"]


@pytest.mark.asyncio
async def test_redis_list_iadd_empty_list_with_pipeline_edge_case():
    # Arrange
    model = ComprehensiveTestModel(tags=["existing"])
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.tags += []

        # Assert - Nothing should change
        loaded_model = await ComprehensiveTestModel.aget(model.key)
        assert loaded_model.tags == ["existing"]

    # Assert - List should remain unchanged
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.tags == ["existing"]


@pytest.mark.asyncio
async def test_redis_list_combined_setitem_and_iadd_with_pipeline_sanity():
    # Arrange
    model = ComprehensiveTestModel(tags=["first", "second"])
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.tags[0] = "modified_first"
        redis_model.tags += ["third", "fourth"]

        # Assert - Changes should not be applied yet
        loaded_model = await ComprehensiveTestModel.aget(model.key)
        assert loaded_model.tags == ["first", "second"]

    # Assert - All changes should be applied after pipeline
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.tags == ["modified_first", "second", "third", "fourth"]
