import pytest
import pytest_asyncio

from rapyer.types.external import FieldTrait
from rapyer.types.redis_set import RedisSet
from tests.models.special_types import (
    AutoMappedSetModel,
    GenericRedisSetModel,
    ListOfSetsModel,
    OptionalRedisSetModel,
)

SET_INIT_PARAMS = [
    [GenericRedisSetModel[str], ["alpha", "beta", "gamma"]],
    [GenericRedisSetModel[int], [10, 20, 30]],
    [GenericRedisSetModel[float], [1.1, 2.72, 3.14]],
    [GenericRedisSetModel[bool], [True, False]],
]


@pytest_asyncio.fixture
async def saved_set_model(request):
    model_class, items = request.param
    model = model_class()
    await model.asave()
    for value in items:
        await model.tags.aadd(value)
    return model, items


@pytest.mark.parametrize(["model_class", "items"], SET_INIT_PARAMS)
@pytest.mark.asyncio
async def test_set_save_and_aadd_persists_members(
    real_redis_client,
    model_class: type[GenericRedisSetModel],
    items,
):
    # Arrange
    model = model_class()
    await model.asave()

    # Act
    for value in items:
        await model.tags.aadd(value)

    # Assert
    assert await model.tags.amembers() == set(items)


@pytest.mark.parametrize(["model_class", "items"], SET_INIT_PARAMS)
@pytest.mark.asyncio
async def test_set_aadd_many_persists_members(
    real_redis_client,
    model_class: type[GenericRedisSetModel],
    items,
):
    # Arrange
    model = model_class()
    await model.asave()

    # Act
    await model.tags.aadd_many(items)

    # Assert
    assert await model.tags.amembers() == set(items)


@pytest.mark.asyncio
async def test_set_aadd_is_idempotent(real_redis_client):
    # Arrange
    model = GenericRedisSetModel[str]()
    await model.asave()

    # Act
    await model.tags.aadd("alpha")
    await model.tags.aadd("alpha")
    await model.tags.aadd("alpha")

    # Assert
    assert await model.tags.asize() == 1


@pytest.mark.parametrize("saved_set_model", SET_INIT_PARAMS, indirect=True)
@pytest.mark.asyncio
async def test_set_acontains(saved_set_model):
    # Arrange
    model, items = saved_set_model

    # Act & Assert
    for value in items:
        assert await model.tags.acontains(value) is True


@pytest.mark.asyncio
async def test_set_acontains_returns_false_for_missing():
    # Arrange
    model = GenericRedisSetModel[str]()
    await model.asave()
    await model.tags.aadd("alpha")

    # Act & Assert
    assert await model.tags.acontains("missing") is False


@pytest.mark.parametrize("saved_set_model", SET_INIT_PARAMS, indirect=True)
@pytest.mark.asyncio
async def test_set_amembers_returns_python_set(saved_set_model):
    # Arrange
    model, items = saved_set_model

    # Act
    members = await model.tags.amembers()

    # Assert
    assert isinstance(members, set)
    assert members == set(items)


@pytest.mark.parametrize("saved_set_model", SET_INIT_PARAMS, indirect=True)
@pytest.mark.asyncio
async def test_set_asize_reflects_operations(saved_set_model):
    # Arrange
    model, items = saved_set_model

    # Act & Assert
    assert await model.tags.asize() == len(items)


@pytest.mark.parametrize("saved_set_model", SET_INIT_PARAMS, indirect=True)
@pytest.mark.asyncio
async def test_set_aremove_specific_value(saved_set_model):
    # Arrange
    model, items = saved_set_model
    value_to_remove = items[0]

    # Act
    removed = await model.tags.aremove(value_to_remove)

    # Assert
    assert removed is True
    assert await model.tags.asize() == len(items) - 1
    assert await model.tags.acontains(value_to_remove) is False

    removed_again = await model.tags.aremove(value_to_remove)
    assert removed_again is False


@pytest.mark.parametrize("saved_set_model", SET_INIT_PARAMS, indirect=True)
@pytest.mark.asyncio
async def test_set_apop_returns_member_and_shrinks(saved_set_model):
    # Arrange
    model, items = saved_set_model
    initial_size = await model.tags.asize()

    # Act
    popped = await model.tags.apop()

    # Assert
    assert popped in set(items)
    assert await model.tags.asize() == initial_size - 1
    assert await model.tags.acontains(popped) is False


@pytest.mark.asyncio
async def test_set_apop_on_empty_returns_none():
    # Arrange
    model = GenericRedisSetModel[str]()
    await model.asave()

    # Act & Assert
    assert await model.tags.apop() is None


@pytest.mark.parametrize("saved_set_model", SET_INIT_PARAMS, indirect=True)
@pytest.mark.asyncio
async def test_set_aclear_removes_all(saved_set_model):
    # Arrange
    model, items = saved_set_model
    assert await model.tags.asize() == len(items)

    # Act
    await model.tags.aclear()

    # Assert
    assert await model.tags.asize() == 0
    assert await model.tags.amembers() == set()


@pytest.mark.parametrize("saved_set_model", SET_INIT_PARAMS, indirect=True)
@pytest.mark.asyncio
async def test_set_adelete_special_clears_key(real_redis_client, saved_set_model):
    # Arrange
    model, items = saved_set_model
    special_key = model.tags.special_key
    assert await real_redis_client.exists(special_key) == 1

    # Act
    await model.tags.adelete_special()

    # Assert
    assert await real_redis_client.exists(special_key) == 0


@pytest.mark.asyncio
async def test_set_aunion_against_other_model():
    # Arrange
    a = GenericRedisSetModel[str]()
    b = GenericRedisSetModel[str]()
    await a.asave()
    await b.asave()
    await a.tags.aadd_many(["alpha", "beta", "gamma"])
    await b.tags.aadd_many(["gamma", "delta"])

    # Act & Assert
    assert await a.tags.aunion(b.tags) == {"alpha", "beta", "gamma", "delta"}


@pytest.mark.asyncio
async def test_set_aintersect_against_other_model():
    # Arrange
    a = GenericRedisSetModel[str]()
    b = GenericRedisSetModel[str]()
    await a.asave()
    await b.asave()
    await a.tags.aadd_many(["alpha", "beta", "gamma"])
    await b.tags.aadd_many(["gamma", "delta"])

    # Act & Assert
    assert await a.tags.aintersect(b.tags) == {"gamma"}


@pytest.mark.asyncio
async def test_set_adifference_against_other_model():
    # Arrange
    a = GenericRedisSetModel[str]()
    b = GenericRedisSetModel[str]()
    await a.asave()
    await b.asave()
    await a.tags.aadd_many(["alpha", "beta", "gamma"])
    await b.tags.aadd_many(["gamma", "delta"])

    # Act & Assert
    assert await a.tags.adifference(b.tags) == {"alpha", "beta"}


@pytest.mark.asyncio
async def test_optional_redis_set_set_after_init(real_redis_client):
    # Arrange
    model = OptionalRedisSetModel()
    assert model.tags is None
    await model.asave()

    # Act
    model.tags = RedisSet()
    await model.tags.aadd("alpha")

    # Assert
    assert await model.tags.amembers() == {"alpha"}


@pytest.mark.asyncio
async def test_auto_mapped_set_field_persists_through_redis_set(real_redis_client):
    # Arrange - `tags: set[str]` should auto-convert to `RedisSet[str]` via ALL_TYPES.
    model = AutoMappedSetModel()
    await model.asave()
    assert isinstance(model.tags, RedisSet)

    # Act
    await model.tags.aadd_many(["python", "redis", "async"])

    # Assert
    assert await model.tags.asize() == 3
    assert await model.tags.acontains("python") is True
    assert await model.tags.amembers() == {"python", "redis", "async"}


# --- Empty-input no-ops / clone ---


@pytest.mark.asyncio
async def test_empty_update_difference_and_aadd_many_are_noops(real_redis_client):
    # Arrange - the empty-input early returns in update / difference_update / aadd_many.
    model = GenericRedisSetModel[str]()
    await model.asave()
    await model.tags.aadd_many(["a", "b"])

    # Act - empty iterables must early-return without touching Redis.
    model.tags.update()
    model.tags.difference_update()
    await model.tags.aadd_many([])

    # Assert
    assert await model.tags.amembers() == {"a", "b"}


@pytest.mark.asyncio
async def test_clone_returns_independent_local_copy(real_redis_client):
    # Arrange - clone() returns a detached local copy of the members.
    model = GenericRedisSetModel[str]()
    await model.asave()
    await model.tags.aadd_many(["a", "b"])

    # Act
    clone = model.tags.clone()

    # Assert
    assert isinstance(clone, RedisSet)
    assert clone is not model.tags
    assert set(clone) == set(model.tags)


@pytest.mark.asyncio
async def test_list_of_bare_redis_sets_is_detected_as_special(real_redis_client):
    # Arrange / Assert - a plain list[RedisSet] is the only construct with an SF inner element.
    annotation = ListOfSetsModel.model_fields["buckets"].annotation
    assert bool(annotation.inner_field_traits() & FieldTrait.OWNS_KEYS) is True

    # Act
    model = ListOfSetsModel()
    await model.asave()
    loaded = await ListOfSetsModel.aget(model.key)

    # Assert
    assert loaded.buckets == []


@pytest.mark.asyncio
async def test_optional_redis_set_gets_its_own_key_excluded_from_the_dump(
    real_redis_client,
):
    # A1 regression: Optional[RedisSet[str]] must classify like RedisSet[str]; members are JSON-encoded.
    expected_field, expected_members = "tags", {'"alpha"'}
    model = OptionalRedisSetModel()
    model.tags = RedisSet()
    await model.tags.aadd("alpha")
    await model.asave()

    # Act
    dump = model.redis_dump()
    special_key = RedisSet.special_field_key(model.key, ".tags")
    members = await real_redis_client.smembers(special_key)

    # Assert
    assert expected_field not in dump
    assert members == expected_members
