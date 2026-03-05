import pytest
from rapyer.types.byte import RedisBytes
from rapyer.types.dct import RedisDict
from rapyer.types.integer import RedisInt
from rapyer.types.lst import RedisList
from rapyer.types.string import RedisStr
from tests.models.redis_types import (
    AnnotatedDirectRedisTypesModel,
    DirectRedisBytesModel,
    DirectRedisDictIntModel,
    DirectRedisDictModel,
    DirectRedisIntModel,
    DirectRedisListIntModel,
    DirectRedisListModel,
    DirectRedisStringModel,
    MixedDirectRedisTypesModel,
)


@pytest.mark.parametrize("test_value", ["hello", "world", "", "test_string"])
def test_direct_redis_str_model_creation_sanity(test_value):
    # Arrange & Act
    model = DirectRedisStringModel(name=test_value)

    # Assert
    assert isinstance(model.name, RedisStr)
    assert model.name.key == model.key
    assert model.name.field_path == ".name"
    assert model.name.json_path == "$.name"
    assert str(model.name) == test_value


@pytest.mark.parametrize("test_value", [0, 1, -1, 100, -100])
def test_direct_redis_int_model_creation_sanity(test_value):
    # Arrange & Act
    model = DirectRedisIntModel(count=test_value)

    # Assert
    assert isinstance(model.count, RedisInt)
    assert model.count.key == model.key
    assert model.count.field_path == ".count"
    assert model.count.json_path == "$.count"
    assert int(model.count) == test_value


@pytest.mark.parametrize("test_value", [b"hello", b"world", b"", b"\x00\x01\x02"])
def test_direct_redis_bytes_model_creation_sanity(test_value):
    # Arrange & Act
    model = DirectRedisBytesModel(data=test_value)

    # Assert
    assert isinstance(model.data, RedisBytes)
    assert model.data.key == model.key
    assert model.data.field_path == ".data"
    assert model.data.json_path == "$.data"
    assert bytes(model.data) == test_value


@pytest.mark.parametrize("test_items", [["a", "b"], ["hello", "world"], [], ["single"]])
def test_direct_redis_list_str_model_creation_sanity(test_items):
    # Arrange & Act
    model = DirectRedisListModel(items=test_items)

    # Assert
    assert isinstance(model.items, RedisList)
    assert model.items.key == model.key
    assert model.items.field_path == ".items"
    assert model.items.json_path == "$.items"
    assert list(model.items) == test_items


@pytest.mark.parametrize("test_numbers", [[1, 2, 3], [0, -1, 100], [], [42]])
def test_direct_redis_list_int_model_creation_sanity(test_numbers):
    # Arrange & Act
    model = DirectRedisListIntModel(numbers=test_numbers)

    # Assert
    assert isinstance(model.numbers, RedisList)
    assert model.numbers.key == model.key
    assert model.numbers.field_path == ".numbers"
    assert model.numbers.json_path == "$.numbers"
    assert list(model.numbers) == test_numbers


@pytest.mark.parametrize(
    "test_dict", [{"a": "b"}, {"key": "value"}, {}, {"x": "y", "z": "w"}]
)
def test_direct_redis_dict_str_model_creation_sanity(test_dict):
    # Arrange & Act
    model = DirectRedisDictModel(metadata=test_dict)

    # Assert
    assert isinstance(model.metadata, RedisDict)
    assert model.metadata.key == model.key
    assert model.metadata.field_path == ".metadata"
    assert model.metadata.json_path == "$.metadata"
    assert dict(model.metadata) == test_dict


@pytest.mark.parametrize("test_dict", [{"a": 1}, {"count": 42}, {}, {"x": 10, "y": 20}])
def test_direct_redis_dict_int_model_creation_sanity(test_dict):
    # Arrange & Act
    model = DirectRedisDictIntModel(counters=test_dict)

    # Assert
    assert isinstance(model.counters, RedisDict)
    assert model.counters.key == model.key
    assert model.counters.field_path == ".counters"
    assert model.counters.json_path == "$.counters"
    assert dict(model.counters) == test_dict


def test_mixed_direct_redis_types_model_creation_sanity():
    # Arrange
    name_val = "test_name"
    count_val = 42
    active_val = True
    tags_val = ["tag1", "tag2"]
    config_val = {"setting1": 10, "setting2": 20}

    # Act
    model = MixedDirectRedisTypesModel(
        name=RedisStr(name_val),
        count=RedisInt(count_val),
        active=active_val,
        tags=tags_val,
        config=config_val,
    )

    # Assert
    assert isinstance(model.name, RedisStr)
    assert isinstance(model.count, RedisInt)
    assert isinstance(model.active, bool)
    assert isinstance(model.tags, RedisList)
    assert isinstance(model.config, RedisDict)

    assert model.name.key == model.key
    assert model.count.key == model.key
    assert model.tags.key == model.key
    assert model.config.key == model.key

    assert model.name.field_path == ".name"
    assert model.count.field_path == ".count"
    assert model.tags.field_path == ".tags"
    assert model.config.field_path == ".config"

    assert model.name.json_path == "$.name"
    assert model.count.json_path == "$.count"
    assert model.tags.json_path == "$.tags"
    assert model.config.json_path == "$.config"

    assert str(model.name) == name_val
    assert int(model.count) == count_val
    assert bool(model.active) == active_val
    assert list(model.tags) == tags_val
    assert dict(model.config) == config_val


def test_annotated_direct_redis_types_model_creation_sanity():
    # Arrange
    title_val = "test_title"
    score_val = 100
    enabled_val = True
    categories_val = ["cat1", "cat2"]
    settings_val = {"key1": "val1", "key2": "val2"}

    # Act
    model = AnnotatedDirectRedisTypesModel(
        title=RedisStr(title_val),
        score=RedisInt(score_val),
        enabled=enabled_val,
        categories=categories_val,
        settings=settings_val,
    )

    # Assert
    assert isinstance(model.title, RedisStr)
    assert isinstance(model.score, RedisInt)
    assert isinstance(model.enabled, bool)
    assert isinstance(model.categories, RedisList)
    assert isinstance(model.settings, RedisDict)

    assert model.title.key == model.key
    assert model.score.key == model.key
    assert model.categories.key == model.key
    assert model.settings.key == model.key

    assert model.title.field_path == ".title"
    assert model.score.field_path == ".score"
    assert model.categories.field_path == ".categories"
    assert model.settings.field_path == ".settings"

    assert model.title.json_path == "$.title"
    assert model.score.json_path == "$.score"
    assert model.categories.json_path == "$.categories"
    assert model.settings.json_path == "$.settings"


def test_direct_redis_types_model_default_values_sanity():
    # Arrange & Act
    model = MixedDirectRedisTypesModel()

    # Assert
    assert isinstance(model.name, RedisStr)
    assert isinstance(model.count, RedisInt)
    assert isinstance(model.active, bool)
    assert isinstance(model.tags, RedisList)
    assert isinstance(model.config, RedisDict)

    assert str(model.name) == "default"
    assert int(model.count) == 0
    assert bool(model.active) == True
    assert list(model.tags) == []
    assert dict(model.config) == {}


def test_direct_redis_types_field_path_nested_model_sanity():
    # Arrange & Act
    model = MixedDirectRedisTypesModel()

    # Assert
    expected_paths = [".name", ".count", ".tags", ".config"]
    actual_paths = [
        model.name.field_path,
        model.count.field_path,
        model.tags.field_path,
        model.config.field_path,
    ]

    assert actual_paths == expected_paths


def test_direct_redis_types_json_path_format_sanity():
    # Arrange & Act
    model = AnnotatedDirectRedisTypesModel(
        categories=["cat1"], settings={"key": "value"}
    )

    # Assert
    expected_json_paths = [
        "$.title",
        "$.score",
        "$.categories",
        "$.settings",
    ]
    actual_json_paths = [
        model.title.json_path,
        model.score.json_path,
        model.categories.json_path,
        model.settings.json_path,
    ]

    assert actual_json_paths == expected_json_paths


def test_direct_redis_types_empty_collections_edge_case():
    # Arrange & Act
    model = DirectRedisListModel(items=[])
    dict_model = DirectRedisDictModel(metadata={})

    # Assert
    assert isinstance(model.items, RedisList)
    assert list(model.items) == []
    assert model.items.field_path == ".items"

    assert isinstance(dict_model.metadata, RedisDict)
    assert dict(dict_model.metadata) == {}
    assert dict_model.metadata.field_path == ".metadata"


def test_direct_redis_types_key_consistency_edge_case():
    # Arrange & Act
    model1 = MixedDirectRedisTypesModel()
    model2 = MixedDirectRedisTypesModel()

    # Assert
    assert model1.key != model2.key

    # Each Redis field should have some key (though might be different for default instances)
    assert model1.name.key is not None
    assert model1.count.key is not None
    assert model2.name.key is not None
    assert model2.count.key is not None

    # When we set values, they should use the model's key
    model3 = MixedDirectRedisTypesModel(name=RedisStr("test"))
    assert model3.name.key == model3.key
