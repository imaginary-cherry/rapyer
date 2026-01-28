import pytest

from tests.models.simple_types import IntModel


@pytest.mark.parametrize("test_values", [42, -100, 0, 999, -999])
@pytest.mark.asyncio
async def test_redis_int_load_functionality_sanity(test_values):
    # Arrange
    model = IntModel()
    await model.asave()
    model.count = test_values
    await model.count.asave()

    # Act
    fresh_model = IntModel()
    fresh_model.pk = model.pk
    loaded_value = await fresh_model.count.aload()

    # Assert
    assert loaded_value == test_values


@pytest.mark.asyncio
async def test_redis_int_load_with_none_value_edge_case():
    # Arrange
    model = IntModel()

    # Act
    loaded_value = await model.count.aload()

    # Assert
    assert loaded_value is None


@pytest.mark.parametrize("redis_values", [4_2, 43])
@pytest.mark.asyncio
async def test_redis_int_load_type_conversion_edge_case(
    real_redis_client, redis_values
):
    # Arrange
    model = IntModel()
    await model.asave()
    await real_redis_client.json().set(model.key, model.count.json_path, redis_values)

    # Act
    fresh_model = IntModel()
    fresh_model.pk = model.pk
    loaded_value = await fresh_model.count.aload()

    # Assert
    assert loaded_value == int(redis_values)


@pytest.mark.asyncio
async def test_redis_int_set_with_wrong_type_edge_case():
    # Arrange
    model = IntModel()

    # Act & Assert
    with pytest.raises(ValueError, match="Input should be a valid integer"):
        model.count = "not an int"


@pytest.mark.asyncio
async def test_redis_int_inheritance_sanity():
    # Arrange & Act
    model = IntModel(count=42)

    # Assert
    from rapyer.types.integer import RedisInt

    assert isinstance(model.count, RedisInt)
    assert isinstance(model.count, int)
    assert model.count == 42
    assert model.count + 10 == 52
    assert model.count - 5 == 37


@pytest.mark.asyncio
async def test_redis_int_clone_functionality_sanity():
    # Arrange
    model = IntModel(count=42)

    # Act
    cloned_int = model.count.clone()

    # Assert
    assert isinstance(cloned_int, int)
    assert not isinstance(cloned_int, type(model.count))
    assert cloned_int == 42


@pytest.mark.asyncio
async def test_redis_int_persistence_across_instances_edge_case():
    # Arrange
    model1 = IntModel(count=100)
    await model1.asave()
    model1.count = 100
    await model1.count.asave()

    # Act
    model2 = IntModel()
    model2.pk = model1.pk
    loaded_value = await model2.count.aload()

    # Assert
    assert loaded_value == 100


@pytest.mark.parametrize(
    "operations",
    [
        [lambda x: x + 10, 52],
        [lambda x: x - 8, 34],
        [lambda x: x * 2, 84],
        [lambda x: x == 42, True],
        [lambda x: x > 40, True],
        [lambda x: x < 40, False],
    ],
)
@pytest.mark.asyncio
async def test_redis_int_arithmetic_operations_sanity(operations):
    # Arrange
    model = IntModel(count=42)
    operation, expected = operations

    # Act
    result = operation(model.count)

    # Assert
    assert result == expected


@pytest.mark.parametrize(
    ["initial_value", "increase_amount", "expected"],
    [
        [0, 1, 1],
        [10, 5, 15],
        [100, -20, 80],
        [-50, 30, -20],
        [0, 0, 0],
        [999, 1, 1000],
        [-999, -1, -1000],
    ],
)
@pytest.mark.asyncio
async def test_redis_int_increase_functionality_sanity(
    initial_value, increase_amount, expected
):
    # Arrange
    model = IntModel()
    await model.asave()
    model.count = initial_value
    await model.count.asave()

    # Act
    result = await model.count.aincrease(increase_amount)

    # Assert
    fresh_model = IntModel()
    fresh_model.pk = model.pk
    loaded_value = await fresh_model.count.aload()
    assert loaded_value == expected
    assert result == expected


@pytest.mark.asyncio
async def test_redis_int_increase_default_amount_sanity():
    # Arrange
    model = IntModel()
    await model.asave()
    model.count = 10
    await model.count.asave()

    # Act
    result = await model.count.aincrease()

    # Assert
    fresh_model = IntModel()
    fresh_model.pk = model.pk
    loaded_value = await fresh_model.count.aload()
    assert loaded_value == 11
    assert result == 11


@pytest.mark.asyncio
async def test_redis_int_increase_on_non_existent_key_edge_case():
    # Arrange
    model = IntModel()
    await model.asave()

    # Act
    result = await model.count.aincrease(5)

    # Assert
    fresh_model = IntModel()
    fresh_model.pk = model.pk
    loaded_value = await fresh_model.count.aload()
    assert loaded_value == 5
    assert result == 5


@pytest.mark.asyncio
async def test_redis_int_increase_multiple_times_sanity():
    # Arrange
    model = IntModel(count=0)
    await model.asave()

    # Act
    result1 = await model.count.aincrease(10)
    result2 = await model.count.aincrease(20)
    result3 = await model.count.aincrease(-5)

    # Assert
    fresh_model = IntModel()
    fresh_model.pk = model.pk
    loaded_value = await fresh_model.count.aload()
    assert result1 == 10
    assert result2 == 30
    assert result3 == 25
    assert loaded_value == 25
