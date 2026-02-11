import pytest
import pytest_asyncio

from rapyer.errors import KeyNotFound
from rapyer.fields import RapyerKey
from tests.models.index_types import IndexTestModel


@pytest_asyncio.fixture
async def create_index(redis_client):
    await IndexTestModel.acreate_index()
    yield
    await IndexTestModel.adelete_index()


@pytest.mark.asyncio
async def test_afind_with_single_key_sanity(redis_client, inserted_test_models):
    # Arrange
    model = inserted_test_models[0]
    key = model.key

    # Act
    found_models = await IndexTestModel.afind(key)

    # Assert
    assert len(found_models) == 1
    assert found_models[0] == model
    assert isinstance(found_models[0].key, RapyerKey)


@pytest.mark.asyncio
async def test_afind_with_multiple_keys_sanity(redis_client, inserted_test_models):
    # Arrange
    models = inserted_test_models[:2]
    keys = [m.key for m in models]

    # Act
    found_models = await IndexTestModel.afind(*keys)

    # Assert
    assert len(found_models) == 2
    for model in models:
        assert model in found_models
    assert all(isinstance(m.key, RapyerKey) for m in found_models)


@pytest.mark.asyncio
async def test_afind_with_keys_without_prefix_sanity(
    redis_client, inserted_test_models
):
    # Arrange
    model = inserted_test_models[0]
    pk_only = model.pk

    # Act
    found_models = await IndexTestModel.afind(pk_only)

    # Assert
    assert len(found_models) == 1
    assert found_models[0] == model
    assert isinstance(found_models[0].key, RapyerKey)


@pytest.mark.asyncio
async def test_afind_with_non_existent_keys_edge_case(
    redis_client, inserted_test_models
):
    # Arrange
    existing_key = inserted_test_models[0].key
    non_existent_key = "IndexTestModel:non_existent_key_12345"

    # Act + Assert
    with pytest.raises(KeyNotFound):
        await IndexTestModel.afind(existing_key, non_existent_key)


@pytest.mark.asyncio
async def test_afind_with_keys_and_expression_ignores_expression(
    redis_client, inserted_test_models
):
    # Arrange
    models = inserted_test_models
    keys = [m.key for m in models]
    IndexTestModel.init_class()

    # Act
    found_models = await IndexTestModel.afind(*keys, IndexTestModel.age > 100)

    # Assert
    assert len(found_models) == 4
    found_names = {m.name for m in found_models}
    assert found_names == {"Alice", "Bob", "Charlie", "David"}
