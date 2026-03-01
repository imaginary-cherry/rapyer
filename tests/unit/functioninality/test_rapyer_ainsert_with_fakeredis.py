import pytest

import rapyer
from tests.models.simple_types import StrModel, IntModel


@pytest.mark.asyncio
async def test_rapyer_aget_returns_model_with_fakeredis_sanity(
    setup_fake_redis_for_models,
    fake_redis_client,
):
    # Arrange
    model = StrModel(name="test_name", description="test_desc")
    await model.asave()

    # Act
    result = await rapyer.aget(model.key)

    # Assert
    assert result.name == "test_name"
    assert result.description == "test_desc"


@pytest.mark.asyncio
async def test_rapyer_ainsert_single_model_with_fakeredis_sanity(
    setup_fake_redis_for_models,
    fake_redis_client,
):
    # Arrange
    model = StrModel(name="test_name", description="test_desc")

    # Act
    await rapyer.ainsert(model)

    # Assert
    retrieved = await StrModel.aget(model.key)
    assert retrieved.name == "test_name"
    assert retrieved.description == "test_desc"


@pytest.mark.asyncio
async def test_rapyer_ainsert_multiple_models_same_class_with_fakeredis_sanity(
    setup_fake_redis_for_models,
    fake_redis_client,
):
    # Arrange
    model1 = StrModel(name="name1", description="desc1")
    model2 = StrModel(name="name2", description="desc2")

    # Act
    res = await rapyer.ainsert(model1, model2)
    retrieved1 = await StrModel.aget(model1.key)
    retrieved2 = await StrModel.aget(model2.key)

    # Assert
    assert res[0].name == retrieved1.name == "name1"
    assert res[1].name == retrieved2.name == "name2"


@pytest.mark.asyncio
async def test_rapyer_ainsert_multiple_models_different_classes_with_fakeredis_sanity(
    setup_fake_redis_for_models,
    fake_redis_client,
):
    # Arrange
    str_model = StrModel(name="test_name", description="test_desc")
    int_model = IntModel(count=42, score=100)

    # Act
    await rapyer.ainsert(str_model, int_model)

    # Assert
    retrieved_str = await StrModel.aget(str_model.key)
    retrieved_int = await IntModel.aget(int_model.key)
    assert retrieved_str.name == "test_name"
    assert retrieved_int.count == 42


@pytest.mark.asyncio
async def test_rapyer_ainsert_returns_models_with_fakeredis_sanity(
    setup_fake_redis_for_models,
    fake_redis_client,
):
    # Arrange
    model1 = StrModel(name="name1", description="desc1")
    model2 = StrModel(name="name2", description="desc2")

    # Act
    result = await rapyer.ainsert(model1, model2)

    # Assert
    assert len(result) == 2
    assert result[0].name == "name1"
    assert result[1].name == "name2"


@pytest.mark.asyncio
async def test_rapyer_aget_returns_model_with_fakeredis_sanity(
    setup_fake_redis_for_models,
    fake_redis_client,
):
    # Arrange
    model = StrModel(name="test_name", description="test_desc")
    await model.asave()

    # Act
    result = await rapyer.aget(model.key)

    # Assert
    assert result.name == "test_name"
    assert result.description == "test_desc"
