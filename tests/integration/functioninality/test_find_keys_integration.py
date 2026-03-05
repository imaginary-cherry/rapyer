import pytest
from tests.models.simple_types import BoolModel, IntModel, StrModel


@pytest.mark.asyncio
async def test_find_keys_returns_only_saved_keys_for_specific_class_sanity():
    # Arrange
    str_model_1 = StrModel(name="test1", description="desc1")
    str_model_2 = StrModel(name="test2", description="desc2")
    str_model_3 = StrModel(name="test3", description="desc3")

    int_model_1 = IntModel(count=10, score=100)
    int_model_2 = IntModel(count=20, score=200)

    bool_model_1 = BoolModel(is_active=True, is_deleted=False)

    await str_model_1.asave()
    await str_model_2.asave()
    await int_model_1.asave()
    await bool_model_1.asave()

    # Act
    str_keys = await StrModel.afind_keys()
    int_keys = await IntModel.afind_keys()
    bool_keys = await BoolModel.afind_keys()

    # Assert
    assert set(str_keys) == {str_model_1.key, str_model_2.key}
    assert set(int_keys) == {int_model_1.key}
    assert set(bool_keys) == {bool_model_1.key}


@pytest.mark.asyncio
async def test_find_keys_empty_results_when_no_saved_models_sanity():
    # Arrange
    str_model_1 = StrModel(name="test1", description="desc1")
    int_model_1 = IntModel(count=10, score=100)
    bool_model_1 = BoolModel(is_active=True, is_deleted=False)

    # Act - Don't save any models, just find keys
    str_keys = await StrModel.afind_keys()
    int_keys = await IntModel.afind_keys()
    bool_keys = await BoolModel.afind_keys()

    # Assert
    assert set(str_keys) == set()
    assert set(int_keys) == set()
    assert set(bool_keys) == set()


@pytest.mark.asyncio
async def test_find_keys_isolation_between_different_model_classes_sanity():
    # Arrange
    str_models = [StrModel(name=f"str_{i}", description=f"desc_{i}") for i in range(3)]
    int_models = [IntModel(count=i * 10, score=i * 100) for i in range(2)]
    bool_models = [
        BoolModel(is_active=bool(i % 2), is_deleted=not bool(i % 2)) for i in range(4)
    ]

    # Act - Save all models
    for model in str_models:
        await model.asave()
    for model in int_models:
        await model.asave()
    for model in bool_models:
        await model.asave()

    # Find keys for each class
    str_keys = await StrModel.afind_keys()
    int_keys = await IntModel.afind_keys()
    bool_keys = await BoolModel.afind_keys()

    # Assert
    assert set(str_keys) == {model.key for model in str_models}
    assert set(int_keys) == {model.key for model in int_models}
    assert set(bool_keys) == {model.key for model in bool_models}
