from uuid import uuid4

import pytest
import rapyer
from rapyer.errors.base import KeyNotFound, RapyerModelDoesntExist
from tests.models.simple_types import StrModel, IntModel


@pytest.mark.asyncio
async def test_rapyer_afind_with_multiple_keys_different_classes_sanity():
    # Arrange
    str_model = StrModel(name="test_user", description="test description")
    int_model = IntModel(count=42, score=100)
    await str_model.asave()
    await int_model.asave()

    # Act
    found_models = await rapyer.afind(str_model.key, int_model.key)

    # Assert
    assert len(found_models) == 2
    assert str_model == found_models[0]
    assert int_model == found_models[1]


@pytest.mark.asyncio
async def test_rapyer_afind_with_empty_input_edge_case():
    # Arrange - no keys provided

    # Act
    found_models = await rapyer.afind()

    # Assert
    assert found_models == []


@pytest.mark.asyncio
async def test_rapyer_afind_with_non_existent_key_edge_case():
    # Arrange
    model = StrModel(name="existing_user", description="existing description")
    await model.asave()
    non_existent_key = "StrModel:non_existent_key_12345"

    # Act + Assert
    with pytest.raises(KeyNotFound):
        await rapyer.afind(model.key, non_existent_key)


@pytest.mark.asyncio
async def test_rapyer_afind_with_unknown_class_name_edge_case():
    # Arrange
    model = StrModel(name="test_user", description="test description")
    await model.asave()
    unknown_class_key = "UnknownClass:some_key"

    # Act + Assert
    with pytest.raises(RapyerModelDoesntExist):
        await rapyer.afind(model.key, unknown_class_key)


@pytest.mark.asyncio
async def test_rapyer_afind_skips_invalid_json_schema_sanity():
    # Arrange
    valid_str_model = StrModel(name="valid_user", description="valid description")
    valid_int_model = IntModel(count=42, score=100)
    await rapyer.ainsert(valid_str_model, valid_int_model)

    redis = IntModel.Meta.redis
    invalid_key = f"IntModel:{uuid4()}"
    await redis.json().set(
        invalid_key, "$", {"count": "not_an_int", "score": "invalid"}
    )

    # Act
    found_models = await rapyer.afind(
        valid_str_model.key, invalid_key, valid_int_model.key
    )

    # Assert
    assert len(found_models) == 2
    assert valid_str_model in found_models
    assert valid_int_model in found_models
