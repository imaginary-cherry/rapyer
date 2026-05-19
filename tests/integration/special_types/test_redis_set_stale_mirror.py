import pytest
import pytest_asyncio

from tests.models.special_types import GenericRedisSetModel


@pytest_asyncio.fixture
async def saved_set_model():
    model = GenericRedisSetModel[str]()
    await model.asave()
    return model


@pytest_asyncio.fixture
async def stale_missing_value_model(saved_set_model):
    # Redis holds "alpha"; the local mirror does not.
    await saved_set_model.tags.aadd("alpha")
    set.discard(saved_set_model.tags, "alpha")
    return saved_set_model


@pytest.mark.asyncio
async def test_apop_succeeds_when_local_mirror_empty_but_redis_populated(
    saved_set_model,
):
    # Arrange
    items = ["alpha", "beta", "gamma"]
    for value in items:
        await saved_set_model.tags.aadd(value)
    set.clear(saved_set_model.tags)
    assert len(saved_set_model.tags) == 0
    assert await saved_set_model.tags.asize() == 3

    # Act
    popped = await saved_set_model.tags.apop()

    # Assert
    assert popped in set(items)
    assert await saved_set_model.tags.asize() == 2
    assert await saved_set_model.tags.acontains(popped) is False


@pytest.mark.asyncio
async def test_aremove_succeeds_when_value_missing_locally_but_present_in_redis(
    stale_missing_value_model,
):
    # Act
    removed = await stale_missing_value_model.tags.aremove("alpha")

    # Assert
    assert removed is True
    assert await stale_missing_value_model.tags.acontains("alpha") is False
    assert await stale_missing_value_model.tags.asize() == 0


@pytest.mark.asyncio
async def test_remove_in_pipeline_succeeds_when_value_missing_locally_but_present_in_redis(
    stale_missing_value_model,
):
    # Act
    async with stale_missing_value_model.apipeline() as piped:
        piped.tags.remove("alpha")

    # Assert
    assert await stale_missing_value_model.tags.acontains("alpha") is False
    assert await stale_missing_value_model.tags.asize() == 0


@pytest.mark.asyncio
async def test_apop_returns_redis_value_when_local_mirror_has_phantom(
    saved_set_model,
):
    # Arrange
    await saved_set_model.tags.aadd_many(["alpha", "beta"])
    set.add(saved_set_model.tags, "phantom")
    assert "phantom" in set(saved_set_model.tags)
    assert await saved_set_model.tags.acontains("phantom") is False

    # Act
    popped = await saved_set_model.tags.apop()

    # Assert
    assert popped in {"alpha", "beta"}
    assert popped != "phantom"
    assert await saved_set_model.tags.asize() == 1
