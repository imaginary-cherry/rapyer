import pytest

from tests.models.collection_types import ComprehensiveTestModel


@pytest.mark.asyncio
async def test_redis_str_operations__changes_outside_pipeline_ignored_sanity():
    # Arrange
    model = ComprehensiveTestModel(name="hello")
    await model.asave()

    # Act - outside pipeline (should be ignored)
    model.name += "_outside"
    model.name += "_ignored"

    # Act - inside pipeline (should take effect)
    async with model.apipeline() as m:
        m.name += "_inside"

    # Assert - only pipeline ops applied
    final = await ComprehensiveTestModel.aget(model.key)
    assert final.name == "hello_inside"


@pytest.mark.asyncio
async def test_redis_str_combined_iadd_and_imul_with_pipeline_sanity():
    # Arrange
    model = ComprehensiveTestModel(name="ab")
    await model.asave()

    # Act
    async with model.apipeline() as m:
        m.name *= 2  # "abab"
        m.name += "_end"  # "abab_end"

        # Assert - changes not visible during pipeline
        loaded = await ComprehensiveTestModel.aget(model.key)
        assert loaded.name == "ab"

    # Assert - all changes applied after pipeline
    final = await ComprehensiveTestModel.aget(model.key)
    assert final.name == "abab_end"
