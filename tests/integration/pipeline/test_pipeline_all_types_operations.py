import pytest

from tests.models.redis_types import PipelineAllTypesTestModel


@pytest.mark.asyncio
async def test_pipeline_list_operations__changes_outside_pipeline_ignored_sanity():
    # Arrange
    model = PipelineAllTypesTestModel(items=["initial"])
    await model.asave()

    # Act - outside pipeline (should NOT affect Redis)
    model.items.append("outside_append")
    model.items.extend(["outside_extend"])
    model.items.insert(0, "outside_insert")
    model.items[0] = "outside_setitem"

    # Act - inside pipeline (SHOULD affect Redis)
    async with model.apipeline() as m:
        m.items.append("inside_append")
        m.items.extend(["inside_extend"])
        m.items.insert(0, "inside_insert")

    # Assert - only pipeline actions took effect
    final = await PipelineAllTypesTestModel.aget(model.key)
    assert final.items == ["inside_insert", "initial", "inside_append", "inside_extend"]


@pytest.mark.asyncio
async def test_pipeline_dict_operations__changes_outside_pipeline_ignored_sanity():
    # Arrange
    model = PipelineAllTypesTestModel(metadata={"initial": "value"})
    await model.asave()

    # Act - outside pipeline (should NOT affect Redis)
    model.metadata["outside_key"] = "outside_value"
    model.metadata.update({"outside_update": "value"})

    # Act - inside pipeline (SHOULD affect Redis)
    async with model.apipeline() as m:
        m.metadata["inside_key"] = "inside_value"
        m.metadata.update({"inside_update": "value"})

    # Assert - only pipeline actions took effect
    final = await PipelineAllTypesTestModel.aget(model.key)
    assert final.metadata == {
        "initial": "value",
        "inside_key": "inside_value",
        "inside_update": "value",
    }


@pytest.mark.asyncio
async def test_pipeline_numeric_add_sub__changes_outside_pipeline_ignored_sanity():
    # Arrange
    model = PipelineAllTypesTestModel(counter=10, amount=100.0)
    await model.asave()

    # Act - outside pipeline (should NOT affect Redis after fix)
    model.counter += 5  # local: 15, redis: 10
    model.counter -= 2  # local: 13, redis: 10
    model.amount += 50.0  # local: 150, redis: 100
    model.amount -= 25.0  # local: 125, redis: 100

    # Act - inside pipeline (SHOULD affect Redis using numincrby)
    async with model.apipeline() as m:
        m.counter += 3  # should do numincrby(10, 3) = 13
        m.amount -= 10.0  # should do numincrby(100, -10) = 90

    # Assert - only pipeline actions took effect (based on original Redis values)
    final = await PipelineAllTypesTestModel.aget(model.key)
    assert final.counter == 13  # 10 + 3
    assert final.amount == 90.0  # 100 - 10


@pytest.mark.asyncio
async def test_pipeline_numeric_mul_div_str__changes_outside_pipeline_ignored_sanity():
    # Arrange
    model = PipelineAllTypesTestModel(counter=10, amount=100.0, name="hello")
    await model.asave()

    # Act - outside pipeline (should NOT affect Redis with Lua scripts)
    model.counter *= 2  # local: 20, redis: 10
    model.amount /= 2  # local: 50.0, redis: 100.0
    model.name += "_outside"  # local: "hello_outside", redis: "hello"

    # Act - inside pipeline (uses Lua scripts with Redis values)
    async with model.apipeline() as m:
        m.counter *= 3  # Lua: 10 * 3 = 30
        m.amount /= 5  # Lua: 100 / 5 = 20.0
        m.name += "_inside"  # Lua: "hello" + "_inside" = "hello_inside"

    # Assert - operations use original Redis values
    final = await PipelineAllTypesTestModel.aget(model.key)
    assert final.counter == 30  # 10 * 3
    assert final.amount == 20.0  # 100 / 5
    assert final.name == "hello_inside"  # NOT "hello_outside_inside"
