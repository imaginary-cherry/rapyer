import pytest

import rapyer
from tests.models.collection_types import ComprehensiveTestModel


@pytest.mark.asyncio
async def test_pipeline__multiple_model_asave__commands_batched_in_single_pipeline(
    real_redis_client,
):
    # Arrange
    model1 = ComprehensiveTestModel(name="model1", counter=1, tags=["tag1"])
    model2 = ComprehensiveTestModel(name="model2", counter=2, tags=["tag2"])
    model3 = ComprehensiveTestModel(name="model3", counter=3, tags=["tag3"])

    model1_key = model1.key
    model2_key = model2.key
    model3_key = model3.key

    # Act
    async with rapyer.apipeline():
        await model1.asave()
        is_model1_saved = await real_redis_client.exists(model1_key)
        # Check that model1 is not saved yet
        assert is_model1_saved == 0

        await model2.asave()
        await model3.asave()

    # Assert - verify all models persisted after single pipeline execute
    loaded1, loaded2, loaded3 = await ComprehensiveTestModel.afind(
        model1_key, model2_key, model3_key
    )
    assert loaded1 == model1
    assert loaded2 == model2
    assert loaded3 == model3


@pytest.mark.asyncio
async def test_nested_apipeline__inner_saves_on_exit__outer_saves_on_exit(
    real_redis_client,
):
    # Arrange
    outer_model = ComprehensiveTestModel(name="outer", counter=10, tags=["outer_tag"])
    inner_model = ComprehensiveTestModel(name="inner", counter=20, tags=["inner_tag"])
    await outer_model.asave()
    await inner_model.asave()

    # Act & Assert - nested pipelines
    async with outer_model.apipeline() as outer:
        outer.counter = 100
        outer.name = "outer_modified"

        async with inner_model.apipeline() as inner:
            inner.counter = 200
            inner.name = "inner_modified"

        # Assert - after inner pipeline exits, inner changes should be saved
        loaded_inner = await ComprehensiveTestModel.aget(inner_model.key)
        assert loaded_inner.counter == 200
        assert loaded_inner.name == "inner_modified"

        # Assert - outer changes should NOT be saved yet (still in outer pipeline)
        loaded_outer = await ComprehensiveTestModel.aget(outer_model.key)
        assert loaded_outer.counter == 10  # Still original
        assert loaded_outer.name == "outer"  # Still original

    # Assert - after outer pipeline exits, outer changes should be saved
    final_outer = await ComprehensiveTestModel.aget(outer_model.key)
    assert final_outer.counter == 100
    assert final_outer.name == "outer_modified"
