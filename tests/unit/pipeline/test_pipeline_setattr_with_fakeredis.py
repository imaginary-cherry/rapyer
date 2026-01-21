import pytest

from tests.models.redis_types import PipelineAllTypesTestModel


@pytest.fixture
def setup_fake_redis(fake_redis_client):
    original_redis = PipelineAllTypesTestModel.Meta.redis
    PipelineAllTypesTestModel.Meta.redis = fake_redis_client
    yield
    PipelineAllTypesTestModel.Meta.redis = original_redis


@pytest.mark.asyncio
async def test_pipeline_setattr_multiple_fields_with_fakeredis_sanity(setup_fake_redis):
    # Arrange
    model = PipelineAllTypesTestModel(
        counter=10,
        amount=10.5,
        name="old",
        data=b"old",
        items=["a"],
        metadata={"a": "1"},
    )
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.counter = 99
        redis_model.amount = 99.9
        redis_model.name = "new"
        redis_model.data = b"new"
        redis_model.items = ["x", "y"]
        redis_model.metadata = {"b": "2"}

    # Assert
    final = await PipelineAllTypesTestModel.aget(model.key)
    assert final.counter == 99
    assert final.amount == 99.9
    assert final.name == "new"
    assert final.data == b"new"
    assert final.items == ["x", "y"]
    assert final.metadata == {"b": "2"}


@pytest.mark.asyncio
async def test_pipeline_setattr_changes_outside_pipeline_ignored_sanity(
    setup_fake_redis,
):
    # Arrange
    model = PipelineAllTypesTestModel(
        counter=10,
        amount=10.5,
        name="original",
    )
    await model.asave()

    # Act - outside pipeline (should NOT affect Redis)
    model.counter = 50
    model.amount = 50.5
    model.name = "outside"

    # Act - inside pipeline (SHOULD affect Redis)
    async with model.apipeline() as redis_model:
        redis_model.counter = 99
        redis_model.name = "inside"

    # Assert - only pipeline changes persist, amount stays at original
    final = await PipelineAllTypesTestModel.aget(model.key)
    assert final.counter == 99
    assert final.amount == 10.5
    assert final.name == "inside"
