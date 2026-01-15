import pytest

from tests.models.collection_types import ComprehensiveTestModel


@pytest.mark.parametrize(
    ["initial_tags", "start", "end", "expected_tags"],
    [
        [["a", "b", "c", "d", "e"], 1, 3, ["a", "d", "e"]],
        [["a", "b", "c", "d", "e"], 0, 2, ["c", "d", "e"]],
        [["a", "b", "c", "d", "e"], 3, 5, ["a", "b", "c"]],
        [["a", "b", "c", "d", "e"], 1, 2, ["a", "c", "d", "e"]],
    ],
)
@pytest.mark.asyncio
async def test_redis_list_remove_range_with_pipeline_sanity(
    initial_tags, start, end, expected_tags
):
    # Arrange
    model = ComprehensiveTestModel(tags=initial_tags)
    await model.asave()

    # Act
    async with model.apipeline():
        model.tags.remove_range(start, end)

        # Assert - Change should not be applied to Redis yet
        loaded_model = await ComprehensiveTestModel.aget(model.key)
        assert loaded_model.tags == initial_tags

    # Assert - Change should be applied after pipeline
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.tags == expected_tags


@pytest.mark.asyncio
async def test_redis_list_remove_range_empty_range_with_pipeline_edge_case():
    # Arrange
    model = ComprehensiveTestModel(tags=["a", "b", "c"])
    await model.asave()

    # Act
    async with model.apipeline():
        model.tags.remove_range(1, 1)

    # Assert - No items should be removed
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.tags == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_redis_list_remove_range_all_items_with_pipeline_edge_case():
    # Arrange
    model = ComprehensiveTestModel(tags=["a", "b", "c"])
    await model.asave()

    # Act
    async with model.apipeline():
        model.tags.remove_range(0, 3)

    # Assert - All items should be removed
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.tags == []


@pytest.mark.asyncio
async def test_redis_list_remove_range_combined_with_other_ops_with_pipeline_sanity():
    # Arrange
    model = ComprehensiveTestModel(tags=["a", "b", "c", "d", "e"])
    await model.asave()

    # Act
    async with model.apipeline():
        model.tags.remove_range(1, 3)
        model.tags.append("f")

        # Assert - Changes should not be applied yet
        loaded_model = await ComprehensiveTestModel.aget(model.key)
        assert loaded_model.tags == ["a", "b", "c", "d", "e"]

    # Assert - All changes should be applied after pipeline
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.tags == ["a", "d", "e", "f"]
