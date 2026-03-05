import pytest

import rapyer
from tests.models.collection_types import ComprehensiveTestModel


@pytest.mark.asyncio
async def test_rapyer_apipeline__use_existing_pipe_true__defers_execution_to_outer(
    real_redis_client,
):
    model = ComprehensiveTestModel(name="original", counter=1, tags=["tag1"])
    await rapyer.ainsert(model)

    async with rapyer.apipeline():
        async with rapyer.apipeline(use_existing_pipe=True):
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
async def test_model_apipeline__use_existing_pipe_true__defers_execution_to_outer(
    real_redis_client,
):
    model1 = ComprehensiveTestModel(name="m1", counter=10, tags=["a"])
    model2 = ComprehensiveTestModel(name="m2", counter=20, tags=["b"])
    await rapyer.ainsert(model1, model2)

    async with rapyer.apipeline():
        async with model1.apipeline(use_existing_pipe=True) as m1:
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
async def test_three_level_nesting__mixed_use_existing_pipe__defers_and_executes_correctly(
    real_redis_client,
):
    model1 = ComprehensiveTestModel(name="m1", counter=1)
    model2 = ComprehensiveTestModel(name="m2", counter=2)
    model3 = ComprehensiveTestModel(name="m3", counter=3)
    await rapyer.ainsert(model1, model2, model3)

    async with rapyer.apipeline():  # Level 1 (outer)
        # Level 2A: use_existing_pipe=True — batches with outer
        async with rapyer.apipeline(use_existing_pipe=True):
            # Level 3A: use_existing_pipe=True — batches with outer (via 2A)
            async with rapyer.apipeline(use_existing_pipe=True):
                m1 = await ComprehensiveTestModel.aget(model1.key)
                m1.name = "m1_updated"

        # Level 2B: use_existing_pipe=False — independent pipe
        async with rapyer.apipeline():
            # Level 3B: use_existing_pipe=True — reuses 2B's independent pipe
            async with rapyer.apipeline(use_existing_pipe=True):
                m2 = await ComprehensiveTestModel.aget(model2.key)
                m2.name = "m2_updated"

        # After 2B exits, model2 should be saved (independent pipe executed)
        loaded2 = await ComprehensiveTestModel.aget(model2.key)
        assert loaded2.name == "m2_updated"

        # model1 and model3 NOT saved yet (batched with outer)
        loaded1 = await ComprehensiveTestModel.aget(model1.key)
        assert loaded1.name == "m1"

        # Level 2C: use_existing_pipe=True — batches with outer
        async with rapyer.apipeline(use_existing_pipe=True):
            # Level 3C: use_existing_pipe=True — batches with outer (via 2C)
            async with rapyer.apipeline(use_existing_pipe=True):
                m3 = await ComprehensiveTestModel.aget(model3.key)
                m3.name = "m3_updated"

        loaded3 = await ComprehensiveTestModel.aget(model3.key)
        assert loaded3.name == "m3"

    # After outer exits — all batched changes applied
    loaded1 = await ComprehensiveTestModel.aget(model1.key)
    assert loaded1.name == "m1_updated"

    loaded2 = await ComprehensiveTestModel.aget(model2.key)
    assert loaded2.name == "m2_updated"

    loaded3 = await ComprehensiveTestModel.aget(model3.key)
    assert loaded3.name == "m3_updated"


@pytest.mark.asyncio
async def test_three_level_nesting__outer_error__finish_changes_in_upper(
    real_redis_client,
):
    model1 = ComprehensiveTestModel(name="m1", counter=1)
    model2 = ComprehensiveTestModel(name="m2", counter=2)
    await rapyer.ainsert(model1, model2)

    async with rapyer.apipeline():  # Level 1 (outer)
        # Level 2: use_existing_pipe=False — independent pipe, error inside
        with pytest.raises(RuntimeError):
            async with rapyer.apipeline(use_existing_pipe=True):
                # Level 3: use_existing_pipe=True — reuses independent pipe
                async with rapyer.apipeline(use_existing_pipe=True):
                    m2 = await ComprehensiveTestModel.aget(model2.key)
                    m2.name = "m2_updated"
                raise RuntimeError("simulated inner error")

    # model2 changes NOT applied (independent pipe errored, never executed)
    loaded2 = await ComprehensiveTestModel.aget(model2.key)
    assert loaded2.name == "m2_updated"


@pytest.mark.asyncio
async def test_nested_apipeline__use_existing_pipe_false__executes_independently(
    real_redis_client,
):
    model = ComprehensiveTestModel(name="original", counter=1)
    await rapyer.ainsert(model)

    async with rapyer.apipeline():
        async with rapyer.apipeline():
            m = await ComprehensiveTestModel.aget(model.key)
            m.name = "inner_modified"
            await m.asave()

        # Inner with use_existing_pipe=False creates its own pipe — executes on exit
        loaded = await ComprehensiveTestModel.aget(model.key)
        assert loaded.name == "inner_modified"


@pytest.mark.asyncio
async def test_rapyer_apipeline__use_existing_pipe_true_no_parent__executes_normally(
    real_redis_client,
):
    model = ComprehensiveTestModel(name="original", counter=1, tags=["tag1"])
    await rapyer.ainsert(model)

    async with rapyer.apipeline(use_existing_pipe=True):
        model.name = "modified"
        model.counter += 99
        model.tags.append("tag2")

    loaded = await ComprehensiveTestModel.aget(model.key)
    assert loaded.name == "modified"
    assert loaded.counter == 100
    assert loaded.tags == ["tag1", "tag2"]
