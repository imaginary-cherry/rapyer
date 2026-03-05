import pytest

from rapyer.types.string import RedisStr
from tests.models.simple_types import StrModel


@pytest.mark.parametrize(
    "test_values",
    ["hello", "world", "", "special chars: !@#$%", "unicode: 你好"],
)
@pytest.mark.asyncio
async def test_redis_str_load_functionality_sanity(test_values):
    # Arrange
    model = StrModel()
    await model.asave()
    model.name = test_values
    await model.name.asave()

    # Act
    fresh_model = StrModel()
    fresh_model.pk = model.pk
    loaded_value = await fresh_model.name.aload()

    # Assert
    assert loaded_value == test_values


@pytest.mark.asyncio
async def test_redis_str_load_with_none_value_edge_case():
    # Arrange
    model = StrModel()

    # Act
    loaded_value = await model.name.aload()

    # Assert
    assert loaded_value is None


@pytest.mark.asyncio
async def test_redis_str_set_with_wrong_type_edge_case():
    # Arrange
    model = StrModel()

    # Act & Assert
    with pytest.raises(ValueError, match="Input should be a valid string"):
        model.name = 42


@pytest.mark.asyncio
async def test_redis_str_inheritance_sanity():
    # Arrange & Act
    model = StrModel(name="hello")

    # Assert
    assert isinstance(model.name, RedisStr)
    assert isinstance(model.name, str)
    assert model.name == "hello"
    assert model.name + " world" == "hello world"
    assert len(model.name) == 5


@pytest.mark.asyncio
async def test_redis_str_clone_functionality_sanity():
    # Arrange
    model = StrModel(name="test")

    # Act
    cloned_str = model.name.clone()

    # Assert
    assert isinstance(cloned_str, str)
    assert not isinstance(cloned_str, type(model.name))
    assert cloned_str == "test"


@pytest.mark.asyncio
async def test_redis_str_persistence_across_instances_edge_case():
    # Arrange
    model1 = StrModel(name="original")
    await model1.asave()
    model1.name = "modified"
    await model1.name.asave()

    # Act
    model2 = StrModel()
    model2.pk = model1.pk
    loaded_value = await model2.name.aload()

    # Assert
    assert loaded_value == "modified"


@pytest.mark.parametrize(
    "operations",
    [
        [lambda x: x.upper(), "HELLO"],
        [lambda x: x.lower(), "hello"],
        [lambda x: x.strip(), "hello"],
        [lambda x: len(x), 5],
        [lambda x: x[1:3], "el"],
        [lambda x: "ell" in x, True],
        [lambda x: x.split("l"), ["he", "", "o"]],
    ],
)
@pytest.mark.asyncio
async def test_redis_str_string_operations_sanity(operations):
    # Arrange
    model = StrModel(name="hello")
    operation, expected = operations

    # Act
    result = operation(model.name)

    # Assert
    assert result == expected


@pytest.mark.asyncio
async def test_redis_str_concatenation_functionality_sanity():
    # Arrange
    model = StrModel(name="hello")

    # Act & Assert
    assert model.name + " world" == "hello world"
    assert "prefix " + model.name == "prefix hello"


@pytest.mark.asyncio
async def test_redis_str_empty_string_functionality_edge_case():
    # Arrange
    model = StrModel(name="")
    await model.asave()

    # Act
    model.name = ""
    await model.name.asave()

    # Assert
    fresh_model = StrModel()
    fresh_model.pk = model.pk
    loaded_value = await fresh_model.name.aload()
    assert loaded_value == ""
    assert len(model.name) == 0
