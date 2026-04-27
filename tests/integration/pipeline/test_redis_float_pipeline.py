import pytest

from tests.models.collection_types import ComprehensiveTestModel


@pytest.mark.asyncio
async def test_redis_float_operations__changes_outside_pipeline_ignored_sanity():
    # Arrange
    model = ComprehensiveTestModel(amount=100.0)
    await model.asave()

    # Act - outside pipeline (should be ignored)
    model.amount += 1000.0
    model.amount *= 5.0

    # Act - inside pipeline (should take effect)
    async with model.apipeline() as m:
        m.amount += 10.0
        m.amount *= 2.0

    # Assert - only pipeline ops applied
    final = await ComprehensiveTestModel.aget(model.key)
    assert final.amount == 220.0
