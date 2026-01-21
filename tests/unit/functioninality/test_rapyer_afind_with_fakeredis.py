import pytest

import rapyer
from rapyer.errors.base import KeyNotFound, RapyerModelDoesntExistError
from tests.models.index_types import IndexTestModel
from tests.models.simple_types import StrModel, IntModel


@pytest.mark.asyncio
async def test_rapyer_afind_with_multiple_keys_different_classes_with_fakeredis_sanity(
    setup_fake_redis_for_models,
    fake_redis_client,
):
    # Arrange
    str_model = StrModel(name="test_name", description="test_desc")
    int_model = IntModel(count=42, score=100)
    await str_model.asave()
    await int_model.asave()

    # Act
    result = await rapyer.afind(str_model.key, int_model.key)

    # Assert
    assert len(result) == 2
    assert result[0].name == "test_name"
    assert result[0].description == "test_desc"
    assert result[1].count == 42
    assert result[1].score == 100


@pytest.mark.asyncio
async def test_model_afind_without_args_returns_all_with_fakeredis_sanity(
    setup_fake_redis_for_models,
    fake_redis_client,
):
    # Arrange
    model1 = StrModel(name="model1", description="desc1")
    model2 = StrModel(name="model2", description="desc2")
    await model1.asave()
    await model2.asave()

    # Act
    result = await StrModel.afind()

    # Assert
    assert len(result) == 2
    names = {m.name for m in result}
    assert names == {"model1", "model2"}


@pytest.mark.asyncio
async def test_model_afind_with_multiple_keys_with_fakeredis_sanity(
    setup_fake_redis_for_models,
    fake_redis_client,
):
    # Arrange
    model1 = StrModel(name="name1", description="desc1")
    model2 = StrModel(name="name2", description="desc2")
    await rapyer.ainsert(model1, model2)

    # Act
    result = await StrModel.afind(model1.key, model2.key)

    # Assert
    assert len(result) == 2
    result_names = {m.name for m in result}
    assert result_names == {"name1", "name2"}


@pytest.mark.asyncio
async def test_model_afind_with_key_without_prefix_with_fakeredis_sanity(
    setup_fake_redis_for_models,
    fake_redis_client,
):
    # Arrange
    model = StrModel(name="test_name", description="test_desc")
    await model.asave()
    key_without_prefix = model.pk

    # Act
    result = await StrModel.afind(key_without_prefix)

    # Assert
    assert len(result) == 1
    assert result[0].name == "test_name"
