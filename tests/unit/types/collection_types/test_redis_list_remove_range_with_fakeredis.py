import pytest

from tests.models.collection_types import ComprehensiveTestModel


@pytest.fixture
def setup_fake_redis(fake_redis_client):
    original_redis = ComprehensiveTestModel.Meta.redis
    ComprehensiveTestModel.Meta.redis = fake_redis_client
    yield
    ComprehensiveTestModel.Meta.redis = original_redis


@pytest.mark.parametrize(
    ["initial_tags", "start", "end", "expected_tags"],
    [
        [["a", "b", "c", "d", "e"], 1, 3, ["a", "d", "e"]],
        [["a", "b", "c", "d", "e"], 3, 5, ["a", "b", "c"]],
        [["a", "b", "c", "d", "e"], 1, 2, ["a", "c", "d", "e"]],
    ],
)
@pytest.mark.asyncio
async def test_redis_list_remove_range_with_fakeredis_sanity(
    setup_fake_redis, initial_tags, start, end, expected_tags
):
    # Arrange
    model = ComprehensiveTestModel(tags=initial_tags)
    await model.asave()

    # Act
    async with model.apipeline():
        model.tags.remove_range(start, end)

    # Assert
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.tags == expected_tags


@pytest.mark.asyncio
async def test_redis_list_remove_range_empty_range_with_fakeredis_edge_case(
    setup_fake_redis,
):
    # Arrange
    model = ComprehensiveTestModel(tags=["a", "d", "c"])
    await model.asave()

    # Act
    async with model.apipeline():
        model.tags.remove_range(1, 1)

    # Assert
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.tags == ["a", "d", "c"]


@pytest.mark.asyncio
async def test_redis_list_remove_range_all_items_with_fakeredis_edge_case(
    setup_fake_redis,
):
    # Arrange
    model = ComprehensiveTestModel(tags=["a", "b", "c"])
    await model.asave()

    # Act
    async with model.apipeline():
        model.tags.remove_range(0, 3)

    # Assert
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.tags == []


@pytest.mark.parametrize(
    ["initial_tags", "start", "end", "expected_tags"],
    [
        [["a", "b", "c", "d", "e"], 3, 100, ["a", "b", "c"]],
        [["a", "b"], 0, 999, []],
    ],
)
@pytest.mark.asyncio
async def test_redis_list_remove_range_end_over_len_with_fakeredis_edge_case(
    setup_fake_redis, initial_tags, start, end, expected_tags
):
    # Arrange
    model = ComprehensiveTestModel(tags=initial_tags)
    await model.asave()

    # Act
    async with model.apipeline():
        model.tags.remove_range(start, end)

    # Assert
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.tags == expected_tags


@pytest.mark.parametrize(
    ["initial_tags", "start", "end"],
    [[["a", "b", "c"], 10, 20]],
)
@pytest.mark.asyncio
async def test_redis_list_remove_range_start_over_len_with_fakeredis_edge_case(
    setup_fake_redis, initial_tags, start, end
):
    # Arrange
    model = ComprehensiveTestModel(tags=initial_tags)
    await model.asave()

    # Act
    async with model.apipeline():
        model.tags.remove_range(start, end)

    # Assert
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.tags == initial_tags


@pytest.mark.parametrize(
    ["initial_tags", "start", "end", "expected_tags"],
    [
        [["a", "b", "c", "d", "e"], -2, 5, ["a", "b", "c"]],
        [["a", "b", "c"], -1, 3, ["a", "b"]],
    ],
)
@pytest.mark.asyncio
async def test_redis_list_remove_range_negative_indices_with_fakeredis_edge_case(
    setup_fake_redis, initial_tags, start, end, expected_tags
):
    # Arrange
    model = ComprehensiveTestModel(tags=initial_tags)
    await model.asave()

    # Act
    async with model.apipeline():
        model.tags.remove_range(start, end)

    # Assert
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.tags == expected_tags
