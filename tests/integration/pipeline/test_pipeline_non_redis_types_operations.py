import pytest

import rapyer
from tests.models.collection_types import MixedTypesModel


@pytest.mark.asyncio
async def test_pipeline_list_any__multiple_operations_single_model__check_atomicity_sanity():
    # Arrange
    model = MixedTypesModel(mixed_list=[{"initial": "value"}])
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.mixed_list.append({"appended": "item"})
        redis_model.mixed_list.extend([{"extended": 1}, {"extended": 2}])
        redis_model.mixed_list.insert(0, {"inserted": "at_start"})
        redis_model.mixed_list[1] = {"replaced": "item"}

        # Assert - changes not visible during pipeline
        loaded = await MixedTypesModel.aget(model.key)
        assert loaded.mixed_list == [{"initial": "value"}]

    # Assert - all changes committed after pipeline
    final = await MixedTypesModel.aget(model.key)
    assert final.mixed_list == [
        {"inserted": "at_start"},
        {"replaced": "item"},
        {"appended": "item"},
        {"extended": 1},
        {"extended": 2},
    ]


@pytest.mark.asyncio
async def test_pipeline_dict_any__multiple_operations_single_model__check_atomicity_sanity():
    # Arrange
    model = MixedTypesModel(mixed_dict={"initial": {"nested": "value"}})
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.mixed_dict["new_key"] = {"new": "value"}
        redis_model.mixed_dict.update({"updated_key": [1, 2, 3]})
        redis_model.mixed_dict["another"] = None

        # Assert - changes not visible during pipeline
        loaded = await MixedTypesModel.aget(model.key)
        assert loaded.mixed_dict == {"initial": {"nested": "value"}}

    # Assert - all changes committed after pipeline
    final = await MixedTypesModel.aget(model.key)
    assert final.mixed_dict == {
        "initial": {"nested": "value"},
        "new_key": {"new": "value"},
        "updated_key": [1, 2, 3],
        "another": None,
    }


@pytest.mark.asyncio
async def test_pipeline_list_and_dict_any__combined_operations_single_model__check_atomicity_sanity():
    # Arrange
    model = MixedTypesModel()
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.mixed_list.append({"list_item": 1})
        redis_model.mixed_dict["dict_key"] = {"dict_value": 2}
        redis_model.mixed_list.extend([[1, 2], [3, 4]])
        redis_model.mixed_dict.update({"bulk1": True, "bulk2": False})

        # Assert - changes not visible during pipeline
        loaded = await MixedTypesModel.aget(model.key)
        assert loaded.mixed_list == []
        assert loaded.mixed_dict == {}

    # Assert - all changes committed after pipeline
    final = await MixedTypesModel.aget(model.key)
    assert final.mixed_list == [{"list_item": 1}, [1, 2], [3, 4]]
    assert final.mixed_dict == {
        "dict_key": {"dict_value": 2},
        "bulk1": True,
        "bulk2": False,
    }


@pytest.mark.asyncio
async def test_pipeline_list_any__multiple_models__check_atomicity_sanity():
    # Arrange
    model1 = MixedTypesModel()
    model2 = MixedTypesModel()
    await rapyer.ainsert(model1, model2)

    # Act
    async with model1.apipeline() as redis_model1:
        redis_model1.mixed_list.append({"model1": "item1"})
        redis_model1.mixed_list.append({"model1": "item2"})

        model2_in_pipeline = await MixedTypesModel.aget(model2.key)
        model2_in_pipeline.mixed_list.append({"model2": "item1"})
        model2_in_pipeline.mixed_list.extend([{"model2": "item2"}, {"model2": "item3"}])

        # Assert - changes not visible during pipeline for both models
        loaded1, loaded2 = await rapyer.afind(model1.key, model2.key)
        assert loaded1.mixed_list == []
        assert loaded2.mixed_list == []

    # Assert - all changes committed after pipeline
    final1, final2 = await rapyer.afind(model1.key, model2.key)
    assert final1.mixed_list == [{"model1": "item1"}, {"model1": "item2"}]
    assert final2.mixed_list == [
        {"model2": "item1"},
        {"model2": "item2"},
        {"model2": "item3"},
    ]


@pytest.mark.asyncio
async def test_pipeline_dict_any__multiple_models__check_atomicity_sanity():
    # Arrange
    model1 = MixedTypesModel()
    model2 = MixedTypesModel()
    await rapyer.ainsert(model1, model2)

    # Act
    async with model1.apipeline() as redis_model1:
        redis_model1.mixed_dict["model1_key1"] = {"nested": "value1"}
        redis_model1.mixed_dict.update({"model1_key2": [1, 2, 3]})

        model2_in_pipeline = await MixedTypesModel.aget(model2.key)
        model2_in_pipeline.mixed_dict["model2_key1"] = {"different": "data"}
        model2_in_pipeline.mixed_dict["model2_key2"] = None

        # Assert - changes not visible during pipeline for both models
        loaded1, loaded2 = await rapyer.afind(model1.key, model2.key)
        assert loaded1.mixed_dict == {}
        assert loaded2.mixed_dict == {}

    # Assert - all changes committed after pipeline
    final1, final2 = await rapyer.afind(model1.key, model2.key)
    assert final1.mixed_dict == {
        "model1_key1": {"nested": "value1"},
        "model1_key2": [1, 2, 3],
    }
    assert final2.mixed_dict == {
        "model2_key1": {"different": "data"},
        "model2_key2": None,
    }


@pytest.mark.asyncio
async def test_pipeline_list_any__iadd_operator__check_atomicity_sanity():
    # Arrange
    model = MixedTypesModel(mixed_list=[{"existing": "item"}])
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.mixed_list += [{"added1": 1}, {"added2": 2}]

        # Assert - changes not visible during pipeline
        loaded = await MixedTypesModel.aget(model.key)
        assert loaded.mixed_list == [{"existing": "item"}]

    # Assert - changes committed after pipeline
    final = await MixedTypesModel.aget(model.key)
    assert final.mixed_list == [{"existing": "item"}, {"added1": 1}, {"added2": 2}]


@pytest.mark.asyncio
async def test_pipeline_list_any__clear_operation__check_atomicity_sanity():
    # Arrange
    model = MixedTypesModel(mixed_list=[{"item1": 1}, {"item2": 2}, {"item3": 3}])
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.mixed_list.clear()

        # Assert - changes not visible during pipeline
        loaded = await MixedTypesModel.aget(model.key)
        assert loaded.mixed_list == [{"item1": 1}, {"item2": 2}, {"item3": 3}]

    # Assert - changes committed after pipeline
    final = await MixedTypesModel.aget(model.key)
    assert final.mixed_list == []


@pytest.mark.asyncio
async def test_pipeline_dict_any__clear_operation__check_atomicity_sanity():
    # Arrange
    model = MixedTypesModel(mixed_dict={"key1": {"val": 1}, "key2": [1, 2]})
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.mixed_dict.clear()

        # Assert - changes not visible during pipeline
        loaded = await MixedTypesModel.aget(model.key)
        assert loaded.mixed_dict == {"key1": {"val": 1}, "key2": [1, 2]}

    # Assert - changes committed after pipeline
    final = await MixedTypesModel.aget(model.key)
    assert final.mixed_dict == {}


@pytest.mark.asyncio
async def test_pipeline_list_any__setitem_various_indices__check_atomicity_sanity():
    # Arrange
    model = MixedTypesModel(mixed_list=[{"idx0": 0}, {"idx1": 1}, {"idx2": 2}])
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.mixed_list[0] = {"new_idx0": "replaced"}
        redis_model.mixed_list[2] = [1, 2, 3]
        redis_model.mixed_list[1] = None

        # Assert - changes not visible during pipeline
        loaded = await MixedTypesModel.aget(model.key)
        assert loaded.mixed_list == [{"idx0": 0}, {"idx1": 1}, {"idx2": 2}]

    # Assert - changes committed after pipeline
    final = await MixedTypesModel.aget(model.key)
    assert final.mixed_list == [{"new_idx0": "replaced"}, None, [1, 2, 3]]


@pytest.mark.asyncio
async def test_pipeline_list_any__ainsert_various_positions__check_atomicity_sanity():
    # Arrange
    model = MixedTypesModel(mixed_list=[{"middle": "item"}])
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.mixed_list.insert(0, {"first": "item"})
        redis_model.mixed_list.insert(2, {"last": "item"})
        redis_model.mixed_list.insert(1, {"second": "item"})

        # Assert - changes not visible during pipeline
        loaded = await MixedTypesModel.aget(model.key)
        assert loaded.mixed_list == [{"middle": "item"}]

    # Assert - changes committed after pipeline
    final = await MixedTypesModel.aget(model.key)
    assert final.mixed_list == [
        {"first": "item"},
        {"second": "item"},
        {"middle": "item"},
        {"last": "item"},
    ]


@pytest.mark.asyncio
async def test_pipeline_list_any__extend_with_various_types__check_atomicity_sanity():
    # Arrange
    initial_data = [{"existing": "item"}, [0, 0, 0]]
    model = MixedTypesModel(mixed_list=initial_data.copy())
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.mixed_list.extend(
            [
                {"dict": "value"},
                [1, 2, 3],
                None,
                "string",
                42,
                3.14,
                True,
            ]
        )

        # Assert - changes not visible during pipeline
        loaded = await MixedTypesModel.aget(model.key)
        assert loaded.mixed_list == initial_data

    # Assert - changes committed after pipeline, initial data preserved
    final = await MixedTypesModel.aget(model.key)
    assert final.mixed_list == [
        {"existing": "item"},
        [0, 0, 0],
        {"dict": "value"},
        [1, 2, 3],
        None,
        "string",
        42,
        3.14,
        True,
    ]


@pytest.mark.asyncio
async def test_pipeline_dict_any__update_with_various_types__check_atomicity_sanity():
    # Arrange
    initial_data = {
        "existing_key": {"nested": "existing"},
        "another_existing": [9, 8, 7],
    }
    model = MixedTypesModel(mixed_dict=initial_data.copy())
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.mixed_dict.update(
            {
                "dict_val": {"nested": "dict"},
                "list_val": [1, 2, 3],
                "none_val": None,
                "str_val": "string",
                "int_val": 42,
                "float_val": 3.14,
                "bool_val": True,
            }
        )

        # Assert - changes not visible during pipeline
        loaded = await MixedTypesModel.aget(model.key)
        assert loaded.mixed_dict == initial_data

    # Assert - changes committed after pipeline, initial data preserved
    final = await MixedTypesModel.aget(model.key)
    assert final.mixed_dict == {
        "existing_key": {"nested": "existing"},
        "another_existing": [9, 8, 7],
        "dict_val": {"nested": "dict"},
        "list_val": [1, 2, 3],
        "none_val": None,
        "str_val": "string",
        "int_val": 42,
        "float_val": 3.14,
        "bool_val": True,
    }


@pytest.mark.asyncio
async def test_pipeline_list_and_dict_any__multiple_models_combined__check_atomicity_sanity():
    # Arrange
    model1 = MixedTypesModel()
    model2 = MixedTypesModel()
    await rapyer.ainsert(model1, model2)

    # Act
    async with model1.apipeline() as redis_model1:
        redis_model1.mixed_list.append({"m1_list": "item"})
        redis_model1.mixed_dict["m1_dict"] = {"nested": True}

        model2_in_pipeline = await MixedTypesModel.aget(model2.key)
        model2_in_pipeline.mixed_list.extend([[1, 2], [3, 4]])
        model2_in_pipeline.mixed_dict.update({"m2_key1": None, "m2_key2": "value"})

        # Assert - changes not visible during pipeline
        loaded1, loaded2 = await rapyer.afind(model1.key, model2.key)
        assert loaded1.mixed_list == []
        assert loaded1.mixed_dict == {}
        assert loaded2.mixed_list == []
        assert loaded2.mixed_dict == {}

    # Assert - all changes committed after pipeline
    final1, final2 = await rapyer.afind(model1.key, model2.key)
    assert final1.mixed_list == [{"m1_list": "item"}]
    assert final1.mixed_dict == {"m1_dict": {"nested": True}}
    assert final2.mixed_list == [[1, 2], [3, 4]]
    assert final2.mixed_dict == {"m2_key1": None, "m2_key2": "value"}


@pytest.mark.asyncio
async def test_pipeline_list_any__clear_then_add__check_atomicity_sanity():
    # Arrange
    model = MixedTypesModel(mixed_list=[{"old": 1}, {"old": 2}])
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.mixed_list.clear()
        redis_model.mixed_list.append({"new": "item"})
        redis_model.mixed_list.extend([{"extended": 1}])

        # Assert - changes not visible during pipeline
        loaded = await MixedTypesModel.aget(model.key)
        assert loaded.mixed_list == [{"old": 1}, {"old": 2}]

    # Assert - changes committed after pipeline
    final = await MixedTypesModel.aget(model.key)
    assert final.mixed_list == [{"new": "item"}, {"extended": 1}]


@pytest.mark.asyncio
async def test_pipeline_dict_any__clear_then_add__check_atomicity_sanity():
    # Arrange
    model = MixedTypesModel(mixed_dict={"old_key": {"old": "value"}})
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.mixed_dict.clear()
        redis_model.mixed_dict["new_key"] = {"new": "value"}
        redis_model.mixed_dict.update({"another": [1, 2, 3]})

        # Assert - changes not visible during pipeline
        loaded = await MixedTypesModel.aget(model.key)
        assert loaded.mixed_dict == {"old_key": {"old": "value"}}

    # Assert - changes committed after pipeline
    final = await MixedTypesModel.aget(model.key)
    assert final.mixed_dict == {"new_key": {"new": "value"}, "another": [1, 2, 3]}


@pytest.mark.asyncio
async def test_pipeline_list_any__deeply_nested_structures__check_atomicity_sanity():
    # Arrange
    model = MixedTypesModel()
    await model.asave()

    deeply_nested = {
        "level1": {"level2": {"level3": {"data": [1, 2, {"inner": "value"}]}}}
    }

    # Act
    async with model.apipeline() as redis_model:
        redis_model.mixed_list.append(deeply_nested)
        redis_model.mixed_list.extend([{"also": {"nested": True}}])

        # Assert - changes not visible during pipeline
        loaded = await MixedTypesModel.aget(model.key)
        assert loaded.mixed_list == []

    # Assert - changes committed after pipeline
    final = await MixedTypesModel.aget(model.key)
    assert final.mixed_list == [deeply_nested, {"also": {"nested": True}}]


@pytest.mark.asyncio
async def test_pipeline_dict_any__deeply_nested_structures__check_atomicity_sanity():
    # Arrange
    model = MixedTypesModel()
    await model.asave()

    deeply_nested = {
        "level1": {"level2": {"level3": {"data": [1, 2, {"inner": "value"}]}}}
    }

    # Act
    async with model.apipeline() as redis_model:
        redis_model.mixed_dict["nested_key"] = deeply_nested
        redis_model.mixed_dict.update({"another_nested": {"a": {"b": {"c": True}}}})

        # Assert - changes not visible during pipeline
        loaded = await MixedTypesModel.aget(model.key)
        assert loaded.mixed_dict == {}

    # Assert - changes committed after pipeline
    final = await MixedTypesModel.aget(model.key)
    assert final.mixed_dict == {
        "nested_key": deeply_nested,
        "another_nested": {"a": {"b": {"c": True}}},
    }


@pytest.mark.parametrize(
    ["value"],
    [
        [{"key": "value"}],
        [{"nested": {"deep": "value"}}],
        [[1, 2, 3]],
        [None],
        ["string_value"],
        [42],
        [3.14],
        [True],
    ],
)
@pytest.mark.asyncio
async def test_pipeline_list_any_append__various_types__check_atomicity_sanity(value):
    # Arrange
    model = MixedTypesModel()
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.mixed_list.append(value)

        # Assert - changes not visible during pipeline
        loaded = await MixedTypesModel.aget(model.key)
        assert loaded.mixed_list == []

    # Assert - changes committed after pipeline
    final = await MixedTypesModel.aget(model.key)
    assert final.mixed_list == [value]


@pytest.mark.asyncio
async def test_pipeline_list_and_dict_any__sync_outside_vs_inside_pipeline__only_pipeline_actions_take_effect_sanity():
    # Arrange
    initial_list = [{"initial": "list_item"}]
    initial_dict = {"initial_key": {"initial": "dict_value"}}
    model = MixedTypesModel(
        mixed_list=initial_list.copy(), mixed_dict=initial_dict.copy()
    )
    await model.asave()

    # Act - do many sync actions outside the pipeline (these should NOT be persisted)
    model.mixed_list.append({"outside_append": 1})
    model.mixed_list.append({"outside_append": 2})
    model.mixed_list.extend([{"outside_extend": 1}, {"outside_extend": 2}])
    model.mixed_list.insert(0, {"outside_insert": "at_start"})
    model.mixed_list[0] = {"outside_setitem": "replaced"}
    model.mixed_dict["outside_key1"] = {"outside": "value1"}
    model.mixed_dict["outside_key2"] = [1, 2, 3]
    model.mixed_dict.update({"outside_update1": None, "outside_update2": True})

    # Act - do some actions inside the pipeline (these SHOULD be persisted)
    async with model.apipeline() as redis_model:
        redis_model.mixed_list.append({"inside_append": "pipeline"})
        redis_model.mixed_list.extend([{"inside_extend": 1}])
        redis_model.mixed_dict["inside_key"] = {"inside": "pipeline_value"}
        redis_model.mixed_dict.update({"inside_update": [4, 5, 6]})

        # Assert - changes not visible during pipeline
        loaded = await MixedTypesModel.aget(model.key)
        assert loaded.mixed_list == initial_list
        assert loaded.mixed_dict == initial_dict

    # Assert - only pipeline actions took effect, sync actions outside were ignored
    final = await MixedTypesModel.aget(model.key)
    assert final.mixed_list == [
        {"initial": "list_item"},
        {"inside_append": "pipeline"},
        {"inside_extend": 1},
    ]
    assert final.mixed_dict == {
        "initial_key": {"initial": "dict_value"},
        "inside_key": {"inside": "pipeline_value"},
        "inside_update": [4, 5, 6],
    }
