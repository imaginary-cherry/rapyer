import pytest

from tests.models.simple_types import BytesModel


@pytest.mark.asyncio
async def test_redis_bytes_iadd_with_pipeline_sanity():
    # Arrange
    model = BytesModel(data=b"hello")
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.data += b" world"

        # Assert - Change should not be applied yet
        loaded_model = await BytesModel.aget(model.key)
        assert loaded_model.data == b"hello"

    # Assert - Change should be applied after pipeline
    final_model = await BytesModel.aget(model.key)
    assert final_model.data == b"hello world"
