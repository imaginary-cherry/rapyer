import pytest

import rapyer
from tests.models.collection_types import ComprehensiveTestModel


@pytest.mark.asyncio
async def test_redis_int_iadd_with_pipeline_after_external_change():
    # Arrange
    model = ComprehensiveTestModel(counter=10)
    await model.asave()

    # Act - Modify the model externally before using += in pipeline
    external_model = await ComprehensiveTestModel.aget(model.key)
    external_model.counter = 50

    async with rapyer.apipeline():
        external_model.counter += 5

    # Assert - Pipeline should increment from the externally-set value (10 + 5 = 55)
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.counter == 15
