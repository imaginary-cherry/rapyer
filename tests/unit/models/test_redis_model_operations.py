from unittest.mock import AsyncMock, MagicMock

import pytest

from rapyer import AtomicRedisModel
from rapyer.types.base import RedisType
from rapyer.types.dct import RedisDict
from rapyer.types.integer import RedisInt
from rapyer.types.lst import RedisList
from rapyer.types.string import RedisStr
from tests.models.collection_types import (
    SimpleListModel,
    SimpleIntListModel,
    SimpleDictModel,
)
from tests.models.complex_types import MiddleModel, InnerMostModel
from tests.models.simple_types import NoneTestModel
from tests.models.unit_types import (
    SimpleIntDictModel,
    MixedCollectionModel,
    OperationsTestModel,
)
from tests.unit.assertions import (
    assert_redis_dict_item_correct,
    assert_redis_list_correct_types,
    assert_redis_list_item_correct,
)


class TestRedisModelDictOperations:
    @pytest.mark.parametrize(
        ["model1_data", "model2_data", "expected_keys"],
        [
            ({"key1": "value1"}, {"key2": "value2"}, ["key1", "key2"]),
            (
                {"shared": "old"},
                {"shared": "new", "extra": "value"},
                ["shared", "extra"],
            ),
            ({}, {"first": "value"}, ["first"]),
        ],
    )
    def test_dict_update_between_models_sanity(
        self, model1_data, model2_data, expected_keys
    ):
        # Arrange
        model1 = SimpleDictModel(data=model1_data)
        model2 = SimpleDictModel(data=model2_data)

        # Act
        model1.data.update(model2.data)

        # Assert
        assert isinstance(model1.data, RedisDict)
        assert isinstance(model2.data, RedisDict)
        assert set(model1.data.keys()) == set(expected_keys)

        for key in model2_data:
            assert_redis_dict_item_correct(
                model1.data, key, model2_data[key], model1.key, f".data.{key}", RedisStr
            )

        for key in model2_data:
            assert_redis_dict_item_correct(
                model2.data, key, model2_data[key], model2.key, f".data.{key}", RedisStr
            )

    @pytest.mark.parametrize(
        ["model1_counts", "model2_counts", "expected_total"],
        [
            ({"count1": 10}, {"count2": 5}, {"count1": 10, "count2": 5}),
            ({"shared": 3}, {"shared": 7}, {"shared": 7}),
            ({}, {"new": 15}, {"new": 15}),
        ],
    )
    def test_int_dict_update_between_models_sanity(
        self, model1_counts, model2_counts, expected_total
    ):
        # Arrange
        model1 = SimpleIntDictModel(counts=model1_counts)
        model2 = SimpleIntDictModel(counts=model2_counts)

        # Act
        model1.counts.update(model2.counts)

        # Assert
        assert isinstance(model1.counts, RedisDict)
        assert isinstance(model2.counts, RedisDict)

        for key, expected_value in expected_total.items():
            assert int(model1.counts[key]) == expected_value
            assert_redis_dict_item_correct(
                model1.counts,
                key,
                str(expected_value),
                model1.key,
                f".counts.{key}",
                RedisInt,
            )

        for key in model2_counts:
            assert_redis_dict_item_correct(
                model2.counts,
                key,
                str(model2_counts[key]),
                model2.key,
                f".counts.{key}",
                RedisInt,
            )

    def test_dict_or_operator_between_models_sanity(self):
        # Arrange
        model1 = SimpleDictModel(data={"key1": "value1"})
        model2 = SimpleDictModel(data={"key2": "value2", "key3": "value3"})

        # Act
        model1.data |= model2.data

        # Assert
        assert isinstance(model1.data, RedisDict)
        assert isinstance(model2.data, RedisDict)
        assert len(model1.data) == 3
        assert "key1" in model1.data and "key2" in model1.data and "key3" in model1.data

        for key in model2.data:
            assert_redis_dict_item_correct(
                model1.data,
                key,
                str(model2.data[key]),
                model1.key,
                f".data.{key}",
                RedisStr,
            )

        for key in model2.data:
            assert_redis_dict_item_correct(
                model2.data,
                key,
                str(model2.data[key]),
                model2.key,
                f".data.{key}",
                RedisStr,
            )


class TestRedisModelIntegerOperations:
    @pytest.mark.parametrize(
        ["model1_count", "model2_count", "expected_result"],
        [
            (10, 5, 15),
            (0, 1, 1),
            (-5, 10, 5),
        ],
    )
    def test_integer_addition_between_models_sanity(
        self, model1_count, model2_count, expected_result
    ):
        # Arrange
        model1 = OperationsTestModel(int_field=model1_count)
        model2 = OperationsTestModel(int_field=model2_count)

        # Act
        model1.int_field += model2.int_field

        # Assert
        assert isinstance(model1.int_field, RedisInt)
        assert isinstance(model2.int_field, RedisInt)
        assert int(model1.int_field) == expected_result
        assert int(model2.int_field) == model2_count

        assert model1.int_field.key == model1.key
        assert model1.int_field.field_path == ".int_field"

        assert model2.int_field.key == model2.key
        assert model2.int_field.field_path == ".int_field"

    @pytest.mark.parametrize(
        ["initial_counts", "add_counts"],
        [
            ({"score": 100}, {"bonus": 50}),
            ({"total": 0}, {"increment": 1}),
            ({"base": 25}, {"multiplier": 4}),
        ],
    )
    def test_integer_dict_cross_model_addition_sanity(self, initial_counts, add_counts):
        # Arrange
        model1 = SimpleIntDictModel(counts=initial_counts)
        model2 = SimpleIntDictModel(counts=add_counts)

        model1_key = list(initial_counts.keys())[0]
        model2_key = list(add_counts.keys())[0]

        # Act
        model1.counts[model1_key] += model2.counts[model2_key]

        # Assert
        assert isinstance(model1.counts[model1_key], RedisInt)
        assert isinstance(model2.counts[model2_key], RedisInt)

        expected_result = initial_counts[model1_key] + add_counts[model2_key]
        assert int(model1.counts[model1_key]) == expected_result
        assert int(model2.counts[model2_key]) == add_counts[model2_key]

        assert model1.counts[model1_key].key == model1.key
        assert model1.counts[model1_key].field_path == f".counts.{model1_key}"

        assert model2.counts[model2_key].key == model2.key
        assert model2.counts[model2_key].field_path == f".counts.{model2_key}"


class TestRedisModelListOperations:
    @pytest.mark.parametrize(
        ["model1_items", "model2_items"],
        [
            (["hello"], ["world"]),
            ([], ["first", "second"]),
            (["a", "b"], ["c", "d", "e"]),
        ],
    )
    def test_list_extend_between_models_sanity(self, model1_items, model2_items):
        # Arrange
        model1 = SimpleListModel(items=model1_items)
        model2 = SimpleListModel(items=model2_items)

        # Act
        model1.items.extend(model2.items)

        # Assert
        assert isinstance(model1.items, RedisList)
        assert isinstance(model2.items, RedisList)
        assert len(model1.items) == len(model1_items) + len(model2_items)
        assert len(model2.items) == len(model2_items)

        assert_redis_list_correct_types(model1.items, model1.key, ".items", RedisStr)
        assert_redis_list_correct_types(model2.items, model2.key, ".items", RedisStr)

    @pytest.mark.parametrize(
        ["model1_items", "model2_items"],
        [
            (["hello"], ["world"]),
            ([], ["first"]),
            (["a"], ["b", "c"]),
        ],
    )
    def test_list_iadd_between_models_sanity(self, model1_items, model2_items):
        # Arrange
        model1 = SimpleListModel(items=model1_items)
        model2 = SimpleListModel(items=model2_items)

        # Act
        model1.items += model2.items

        # Assert
        assert isinstance(model1.items, RedisList)
        assert isinstance(model2.items, RedisList)
        assert len(model1.items) == len(model1_items) + len(model2_items)
        assert len(model2.items) == len(model2_items)

        assert_redis_list_correct_types(model1.items, model1.key, ".items", RedisStr)
        assert_redis_list_correct_types(model2.items, model2.key, ".items", RedisStr)

    @pytest.mark.parametrize(
        ["model1_numbers", "model2_numbers"],
        [
            ([1, 2], [3, 4]),
            ([10], []),
            ([], [5, 6, 7]),
        ],
    )
    def test_int_list_extend_between_models_sanity(
        self, model1_numbers, model2_numbers
    ):
        # Arrange
        model1 = SimpleIntListModel(numbers=model1_numbers)
        model2 = SimpleIntListModel(numbers=model2_numbers)

        # Act
        model1.numbers.extend(model2.numbers)

        # Assert
        assert isinstance(model1.numbers, RedisList)
        assert isinstance(model2.numbers, RedisList)
        assert len(model1.numbers) == len(model1_numbers) + len(model2_numbers)
        assert len(model2.numbers) == len(model2_numbers)

        for idx, item in enumerate(model1.numbers):
            assert isinstance(item, RedisInt)
            assert item.key == model1.key
            assert item.field_path == f".numbers[{idx}]"

        for idx, item in enumerate(model2.numbers):
            assert isinstance(item, RedisInt)
            assert item.key == model2.key
            assert item.field_path == f".numbers[{idx}]"


class TestRedisModelComplexOperations:
    def test_nested_dict_list_operations_between_models_sanity(self):
        # Arrange
        model1 = MixedCollectionModel(str_list=["hello"], int_dict={"count": 10})
        model2 = MixedCollectionModel(str_list=["world", "test"], int_dict={"score": 5})

        # Act - Add items from model2's list to model1's list
        model1.str_list += model2.str_list

        # Act - Update model1's dict with model2's dict
        model1.int_dict.update(model2.int_dict)

        # Assert list operations
        assert isinstance(model1.str_list, RedisList)
        assert len(model1.str_list) == 3

        assert_redis_list_correct_types(
            model1.str_list, model1.key, ".str_list", RedisStr
        )

        # Assert dict operations
        assert isinstance(model1.int_dict, RedisDict)
        assert len(model1.int_dict) == 2
        assert "count" in model1.int_dict and "score" in model1.int_dict

        for key in model1.int_dict:
            assert isinstance(model1.int_dict[key], RedisInt)
            assert_redis_dict_item_correct(
                model1.int_dict,
                key,
                str(model1.int_dict[key]),
                model1.key,
                f".int_dict.{key}",
                RedisInt,
            )

        # Assert model2 remains unchanged
        assert len(model2.str_list) == 2
        assert len(model2.int_dict) == 1

        assert_redis_list_correct_types(
            model2.str_list, model2.key, ".str_list", RedisStr
        )

        for key in model2.int_dict:
            assert_redis_dict_item_correct(
                model2.int_dict,
                key,
                str(model2.int_dict[key]),
                model2.key,
                f".int_dict.{key}",
                RedisInt,
            )

    def test_cross_model_nested_access_operations_sanity(self):
        # Arrange
        model1 = MixedCollectionModel(str_dict={"data": "hello"}, int_list=[1, 2, 3])
        model2 = MixedCollectionModel(str_dict={"nested": "world"}, int_list=[10])

        # Act - Complex nested operations
        model1.str_dict.update({"new_key": str(model2.str_dict["nested"])})
        model1.int_list[0] += model2.int_list[0]

        # Assert
        assert isinstance(model1.str_dict, RedisDict)
        assert isinstance(model1.int_list, RedisList)

        assert "new_key" in model1.str_dict
        assert str(model1.str_dict["new_key"]) == "world"
        assert int(model1.int_list[0]) == 11

        assert_redis_dict_item_correct(
            model1.str_dict,
            "new_key",
            "world",
            model1.key,
            ".str_dict.new_key",
            RedisStr,
        )

        assert_redis_list_item_correct(
            model1.int_list, 0, "11", model1.key, ".int_list[0]", RedisInt
        )

        # Assert model2 remains unchanged
        assert str(model2.str_dict["nested"]) == "world"
        assert int(model2.int_list[0]) == 10

        assert_redis_dict_item_correct(
            model2.str_dict, "nested", "world", model2.key, ".str_dict.nested", RedisStr
        )

        assert_redis_list_item_correct(
            model2.int_list, 0, "10", model2.key, ".int_list[0]", RedisInt
        )


class TestRedisModelAupdateOperations:
    @pytest.mark.parametrize(
        ["update_data"],
        [
            [{"str_field": "updated_string", "int_field": 42}],
            [{"str_field": "new_value"}],
            [{"int_field": 100, "bool_field": False}],
        ],
    )
    @pytest.mark.asyncio
    async def test_aupdate_redis_types_mocks_pipeline_correctly_sanity(
        self, update_data
    ):
        # Arrange
        model = OperationsTestModel(str_field="original", int_field=10, bool_field=True)

        mock_pipeline = MagicMock()
        mock_json = MagicMock()
        mock_pipeline.json.return_value = mock_json
        mock_pipeline.execute = AsyncMock()

        mock_redis = MagicMock()
        mock_redis.pipeline.return_value.__aenter__.return_value = mock_pipeline
        mock_redis.pipeline.return_value.__aexit__.return_value = AsyncMock()

        # Mock the model's Meta.redis
        model.Meta.redis = mock_redis

        # Act
        await model.aupdate(**update_data)

        # Assert
        mock_redis.pipeline.assert_called_once()
        mock_pipeline.json.assert_called()

        # Verify pipeline.json().set was called for each updated field with correct paths
        assert mock_json.set.call_count == len(update_data)

        call_args_list = [call[0] for call in mock_json.set.call_args_list]
        expected_field_paths = [f"$.{field_name}" for field_name in update_data.keys()]

        # Check that all calls use the correct key and field paths
        for call_args in call_args_list:
            redis_key, json_path, value = call_args
            assert redis_key == model.key
            assert json_path in expected_field_paths

        mock_pipeline.execute.assert_called_once()


class TestRedisModelUpdateOperations:
    @pytest.mark.parametrize(
        ["initial_data", "update_data"],
        [
            ({"name": "old_name", "count": 5}, {"name": "new_name", "count": 10}),
            ({"name": "test", "count": 0}, {"name": "updated", "count": 100}),
            ({"name": "", "count": 1}, {"name": "fresh", "count": 50}),
        ],
    )
    def test_update_redis_types_sanity(self, initial_data, update_data):
        # Arrange
        from tests.models.redis_types import MixedDirectRedisTypesModel

        model = MixedDirectRedisTypesModel(**initial_data)

        # Act
        model.update(**update_data)

        # Assert
        assert isinstance(model.name, RedisStr)
        assert isinstance(model.count, RedisInt)

        assert model.name == update_data["name"]
        assert model.count == update_data["count"]

        assert model.name.key == model.key
        assert model.name.json_path == "$.name"

        assert model.count.key == model.key
        assert model.count.json_path == "$.count"

    @pytest.mark.parametrize(
        ["field_name", "initial_value", "update_value"],
        [
            ("value", 10, 20),
            ("value", 5, 15),
            ("value", 1, 99),
        ],
    )
    def test_update_unsupported_types_sanity(
        self, field_name, initial_value, update_value
    ):
        # Arrange
        from tests.models.pickle_types import ModelWithUnserializableFields

        model = ModelWithUnserializableFields(**{field_name: initial_value})

        # Act
        model.update(**{field_name: update_value})

        # Assert
        assert isinstance(getattr(model, field_name), int)
        assert getattr(model, field_name) == update_value

        # Verify unsupported types remain as their original types
        assert isinstance(model.model_type, type) or model.model_type is None
        assert isinstance(model.callable_field, type) or model.callable_field is None

    @pytest.mark.parametrize(
        ["update_data"],
        [
            [{"optional_string": "updated", "optional_int": 42}],
            [{"optional_bytes": b"data"}],
            [{"optional_list": ["item"]}],
            [{"optional_dict": {"key": "value"}}],
        ],
    )
    def test_update_none_default_values_sanity(self, update_data):
        # Arrange
        model = NoneTestModel()

        # Act
        model.update(**update_data)

        # Assert
        for field_name, expected_value in update_data.items():
            actual_value = getattr(model, field_name)
            assert actual_value == expected_value

            # Check types - some become Redis types, others remain normal Python types
            assert isinstance(actual_value, RedisType)
            assert actual_value.key == model.key
            assert actual_value.json_path == f"$.{field_name}"

    @pytest.mark.parametrize(
        ["update_data"],
        [[{"optional_bytes": b"data"}]],
    )
    def test_update_none_values_with_non_redis_field(self, update_data):
        # Arrange
        model = NoneTestModel()

        # Act
        model.update(**update_data)

        # Assert
        for field_name, expected_value in update_data.items():
            actual_value = getattr(model, field_name)
            assert actual_value == expected_value

    @pytest.mark.parametrize(
        ["updated_middle"],
        [
            [{"tags": ["new_item"], "inner_model": {"lst": ["1"]}}],
            [MiddleModel(tags=["new_item"], inner_model=InnerMostModel(lst=["1"]))],
        ],
    )
    def test_update_nested_model_sanity(self, updated_middle):
        # Arrange
        from tests.models.complex_types import OuterModel

        model = OuterModel()

        # Act
        model.update(middle_model=updated_middle)

        # Assert
        # Check field update
        assert model.middle_model.tags == ["new_item"]
        assert model.middle_model.inner_model.lst == ["1"]

        assert (
            model.middle_model.inner_model.lst.json_path
            == "$.middle_model.inner_model.lst"
        )
        assert model.middle_model.tags.json_path == "$.middle_model.tags"
        assert isinstance(model.middle_model.inner_model, AtomicRedisModel)
        assert isinstance(model.middle_model, AtomicRedisModel)

    @pytest.mark.parametrize(
        ["base_data", "update_data"],
        [
            ({"name": "base_user", "age": 25}, {"name": "updated_user", "age": 30}),
            (
                {"email": "old@example.com", "role": "user"},
                {"email": "new@example.com"},
            ),
            (
                {"is_active": False, "tags": ["old"]},
                {"tags": ["new", "updated"]},
            ),
        ],
    )
    def test_update_inheritance_parent_fields_sanity(self, base_data, update_data):
        # Arrange
        from tests.models.inheritance_types import AdminUserModel

        model = AdminUserModel(**base_data)

        # Act
        model.update(**update_data)

        # Assert
        for field_name, expected_value in update_data.items():
            actual_value = getattr(model, field_name)
            assert actual_value == expected_value
            assert isinstance(actual_value, RedisType)
            assert actual_value.key == model.key
            assert actual_value.json_path == f"$.{field_name}"

    @pytest.mark.parametrize(
        ["initial_data", "update_data"],
        [
            ({"name": "old_name", "score": 5}, {"name": "new_name", "score": 10}),
            ({"name": "test", "score": 0}, {"name": "updated", "score": 100}),
            ({"name": "", "score": 1}, {"name": "fresh", "score": 50}),
        ],
    )
    def test_update_non_redis_types_sanity(self, initial_data, update_data):
        # Arrange
        from tests.models.simple_types import StrModel, IntModel

        str_model = StrModel(name=initial_data["name"])
        int_model = IntModel(score=initial_data["score"])

        # Act
        str_model.update(name=update_data["name"])
        int_model.update(score=update_data["score"])

        # Assert
        assert isinstance(str_model.name, str)
        assert isinstance(int_model.score, int)

        assert str_model.name == update_data["name"]
        assert int_model.score == update_data["score"]
