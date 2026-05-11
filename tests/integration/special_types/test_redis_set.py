import json

import pytest
import pytest_asyncio

from rapyer.types.redis_set import RedisSet
from tests.models.special_types import (
    AutoMappedSetModel,
    GenericRedisSetModel,
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
    model = model_class()
    await model.asave()

    for value in items:
        await model.tags.aadd(value)

    raw = await real_redis_client.smembers(model.tags.special_key)
    decoded = {json.loads(m) for m in raw}
    assert decoded == set(items)


@pytest.mark.parametrize(["model_class", "items"], SET_INIT_PARAMS)
@pytest.mark.asyncio
async def test_set_aadd_many_persists_members(
    real_redis_client,
    model_class: type[GenericRedisSetModel],
    items,
):
    model = model_class()
    await model.asave()

    await model.tags.aadd_many(items)

    decoded = {
        json.loads(m) for m in await real_redis_client.smembers(model.tags.special_key)
    }
    assert decoded == set(items)


@pytest.mark.asyncio
async def test_set_aadd_is_idempotent(real_redis_client):
    model = GenericRedisSetModel[str]()
    await model.asave()

    await model.tags.aadd("alpha")
    await model.tags.aadd("alpha")
    await model.tags.aadd("alpha")

    assert await model.tags.asize() == 1


@pytest.mark.parametrize("saved_set_model", SET_INIT_PARAMS, indirect=True)
@pytest.mark.asyncio
async def test_set_acontains(saved_set_model):
    model, items = saved_set_model
    for value in items:
        assert await model.tags.acontains(value) is True


@pytest.mark.asyncio
async def test_set_acontains_returns_false_for_missing():
    model = GenericRedisSetModel[str]()
    await model.asave()
    await model.tags.aadd("alpha")

    assert await model.tags.acontains("missing") is False


@pytest.mark.parametrize("saved_set_model", SET_INIT_PARAMS, indirect=True)
@pytest.mark.asyncio
async def test_set_amembers_returns_python_set(saved_set_model):
    model, items = saved_set_model
    members = await model.tags.amembers()
    assert isinstance(members, set)
    assert members == set(items)


@pytest.mark.parametrize("saved_set_model", SET_INIT_PARAMS, indirect=True)
@pytest.mark.asyncio
async def test_set_asize_reflects_operations(saved_set_model):
    model, items = saved_set_model
    assert await model.tags.asize() == len(items)


@pytest.mark.parametrize("saved_set_model", SET_INIT_PARAMS, indirect=True)
@pytest.mark.asyncio
async def test_set_aremove_specific_value(saved_set_model):
    model, items = saved_set_model
    value_to_remove = items[0]

    removed = await model.tags.aremove(value_to_remove)
    assert removed is True

    assert await model.tags.asize() == len(items) - 1
    assert await model.tags.acontains(value_to_remove) is False

    removed_again = await model.tags.aremove(value_to_remove)
    assert removed_again is False


@pytest.mark.parametrize("saved_set_model", SET_INIT_PARAMS, indirect=True)
@pytest.mark.asyncio
async def test_set_apop_returns_member_and_shrinks(saved_set_model):
    model, items = saved_set_model
    initial_size = await model.tags.asize()

    popped = await model.tags.apop()
    assert popped in set(items)

    assert await model.tags.asize() == initial_size - 1
    assert await model.tags.acontains(popped) is False


@pytest.mark.asyncio
async def test_set_apop_on_empty_returns_none():
    model = GenericRedisSetModel[str]()
    await model.asave()
    assert await model.tags.apop() is None


@pytest.mark.parametrize("saved_set_model", SET_INIT_PARAMS, indirect=True)
@pytest.mark.asyncio
async def test_set_aclear_removes_all(saved_set_model):
    model, items = saved_set_model
    assert await model.tags.asize() == len(items)

    await model.tags.aclear()

    assert await model.tags.asize() == 0
    assert await model.tags.amembers() == set()


@pytest.mark.parametrize("saved_set_model", SET_INIT_PARAMS, indirect=True)
@pytest.mark.asyncio
async def test_set_adelete_special_clears_key(real_redis_client, saved_set_model):
    model, items = saved_set_model
    special_key = model.tags.special_key
    assert await real_redis_client.exists(special_key) == 1

    await model.tags.adelete_special()

    assert await real_redis_client.exists(special_key) == 0


@pytest.mark.asyncio
async def test_set_aunion_against_other_model():
    a = GenericRedisSetModel[str]()
    b = GenericRedisSetModel[str]()
    await a.asave()
    await b.asave()
    await a.tags.aadd_many(["alpha", "beta", "gamma"])
    await b.tags.aadd_many(["gamma", "delta"])

    assert await a.tags.aunion(b.tags) == {"alpha", "beta", "gamma", "delta"}


@pytest.mark.asyncio
async def test_set_aintersect_against_other_model():
    a = GenericRedisSetModel[str]()
    b = GenericRedisSetModel[str]()
    await a.asave()
    await b.asave()
    await a.tags.aadd_many(["alpha", "beta", "gamma"])
    await b.tags.aadd_many(["gamma", "delta"])

    assert await a.tags.aintersect(b.tags) == {"gamma"}


@pytest.mark.asyncio
async def test_set_adifference_against_other_model():
    a = GenericRedisSetModel[str]()
    b = GenericRedisSetModel[str]()
    await a.asave()
    await b.asave()
    await a.tags.aadd_many(["alpha", "beta", "gamma"])
    await b.tags.aadd_many(["gamma", "delta"])

    assert await a.tags.adifference(b.tags) == {"alpha", "beta"}


@pytest.mark.asyncio
async def test_optional_redis_set_set_after_init(real_redis_client):
    model = OptionalRedisSetModel()
    assert model.tags is None

    await model.asave()

    model.tags = RedisSet()
    await model.tags.aadd("alpha")

    assert await model.tags.amembers() == {"alpha"}


@pytest.mark.asyncio
async def test_auto_mapped_set_field_persists_through_redis_set(real_redis_client):
    # `tags: set[str]` should be auto-converted to `RedisSet[str]` via ALL_TYPES.
    model = AutoMappedSetModel()
    await model.asave()

    assert isinstance(model.tags, RedisSet)

    await model.tags.aadd_many(["python", "redis", "async"])
    assert await model.tags.asize() == 3
    assert await model.tags.acontains("python") is True
    assert await model.tags.amembers() == {"python", "redis", "async"}


