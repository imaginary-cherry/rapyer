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
    assert str_model in found_models
    assert int_model in found_models


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
async def test_rapyer_afind_preserves_model_types_sanity():
    # Arrange
    str_model = StrModel(name="str_test", description="string model")
    int_model = IntModel(count=99, score=200)
    await str_model.asave()
    await int_model.asave()

    # Act
    found_models = await rapyer.afind(str_model.key, int_model.key)

    # Assert
    str_models = [m for m in found_models if isinstance(m, StrModel)]
    int_models = [m for m in found_models if isinstance(m, IntModel)]
    assert len(str_models) == 1
    assert len(int_models) == 1
    assert str_models[0].name == "str_test"
    assert int_models[0].count == 99
