import pytest

import rapyer
from tests.models.collection_types import ComprehensiveTestModel


@pytest.mark.asyncio
async def test_rapyer_apipeline__use_exising_pipe_true__defers_execution_to_outer(
    real_redis_client,
):
    model = ComprehensiveTestModel(name="original", counter=1, tags=["tag1"])
    await rapyer.ainsert(model)

    async with rapyer.apipeline():
        async with rapyer.apipeline(use_exising_pipe=True):
            m = await ComprehensiveTestModel.aget(model.key)
            m.name += "_modified"
            m.counter += 98
            m.tags.append("tag2")

        # Inner exited but outer hasn't — changes should NOT be in Redis yet
        loaded = await ComprehensiveTestModel.aget(model.key)
        assert loaded.name == "original"
        assert loaded.counter == 1
        assert loaded.tags == ["tag1"]

    # After outer exits — changes should be applied
    loaded = await ComprehensiveTestModel.aget(model.key)
    assert loaded.name == "original_modified"
    assert loaded.counter == 99
    assert loaded.tags == ["tag1", "tag2"]


@pytest.mark.asyncio
async def test_model_apipeline__use_exising_pipe_true__defers_execution_to_outer(
    real_redis_client,
):
    model1 = ComprehensiveTestModel(name="m1", counter=10, tags=["a"])
    model2 = ComprehensiveTestModel(name="m2", counter=20, tags=["b"])
    await rapyer.ainsert(model1, model2)

    async with rapyer.apipeline():
        async with model1.apipeline(use_exising_pipe=True) as m1:
            m1.name = "m1_updated"
            m1.counter += 90
            m1.metadata["key1"] = "value1"

        # Inner exited but outer hasn't — model1 changes should NOT be in Redis yet
        loaded = await ComprehensiveTestModel.aget(model1.key)
        assert loaded.name == "m1"
        assert loaded.counter == 10
        assert loaded.metadata == {}

    # After outer exits — changes should be applied
    loaded1 = await ComprehensiveTestModel.aget(model1.key)
    assert loaded1.name == "m1_updated"
    assert loaded1.counter == 100
    assert loaded1.metadata == {"key1": "value1"}

    # model2 should be unchanged
    loaded2 = await ComprehensiveTestModel.aget(model2.key)
    assert loaded2.name == "m2"
    assert loaded2.counter == 20


@pytest.mark.asyncio
async def test_nested_pipelines__mixed_use_exising_pipe__error_in_independent_pipe(
    real_redis_client,
):
    model1 = ComprehensiveTestModel(name="m1", counter=1)
    model2 = ComprehensiveTestModel(name="m2", counter=2)
    model3 = ComprehensiveTestModel(name="m3", counter=3)
    await rapyer.ainsert(model1, model2, model3)

    async with rapyer.apipeline():
        # Inner A: use_exising_pipe=True — batches with outer
        async with rapyer.apipeline(use_exising_pipe=True):
            m1 = await ComprehensiveTestModel.aget(model1.key)
            m1.name = "m1_updated"
            await m1.asave()

        # Inner B: use_exising_pipe=False — independent pipe, will error
        with pytest.raises(RuntimeError):
            async with rapyer.apipeline(use_exising_pipe=False):
                m2 = await ComprehensiveTestModel.aget(model2.key)
                m2.name = "m2_updated"
                await m2.asave()
                raise RuntimeError("simulated error")

        # Inner C: use_exising_pipe=True — batches with outer
        async with rapyer.apipeline(use_exising_pipe=True):
            m3 = await ComprehensiveTestModel.aget(model3.key)
            m3.name = "m3_updated"
            await m3.asave()

    # model1 and model3 changes applied (batched with outer)
    loaded1 = await ComprehensiveTestModel.aget(model1.key)
    assert loaded1.name == "m1_updated"

    # model2 changes NOT applied (independent pipe rolled back on error)
    loaded2 = await ComprehensiveTestModel.aget(model2.key)
    assert loaded2.name == "m2"

    loaded3 = await ComprehensiveTestModel.aget(model3.key)
    assert loaded3.name == "m3_updated"


@pytest.mark.asyncio
async def test_nested_apipeline__use_exising_pipe_false__executes_independently(
    real_redis_client,
):
    model = ComprehensiveTestModel(name="original", counter=1)
    await rapyer.ainsert(model)

    async with rapyer.apipeline():
        async with rapyer.apipeline(use_exising_pipe=False):
            m = await ComprehensiveTestModel.aget(model.key)
            m.name = "inner_modified"
            await m.asave()

        # Inner with use_exising_pipe=False creates its own pipe — executes on exit
        loaded = await ComprehensiveTestModel.aget(model.key)
        assert loaded.name == "inner_modified"
