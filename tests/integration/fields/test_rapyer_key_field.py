import pytest

from rapyer.fields import RapyerKey
from rapyer.types.dct import RedisDict
from rapyer.types.lst import RedisList
from tests.models.redis_types import (
    DictOfListsRapyerKeyModel,
    ListOfDictsRapyerKeyModel,
    RapyerKeyFieldModel,
)


@pytest.fixture
def rapyer_key_model():
    return RapyerKeyFieldModel(
        single_key=RapyerKey("SomeModel:123"),
        key_list=[RapyerKey("ModelA:1"), RapyerKey("ModelA:2")],
        key_dict={"ref1": RapyerKey("ModelB:10"), "ref2": RapyerKey("ModelB:20")},
        plain_key_list=[RapyerKey("ModelC:1"), RapyerKey("ModelC:2")],
        plain_key_dict={"ref1": RapyerKey("ModelD:10"), "ref2": RapyerKey("ModelD:20")},
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["field_name", "expected_type"],
    [
        ["key_list", RedisList],
        ["plain_key_list", list],
        ["key_dict", RedisDict],
        ["plain_key_dict", dict],
    ],
)
async def test_rapyer_key_collection_field__save_and_get__items_are_rapyer_keys(
    real_redis_client, rapyer_key_model, field_name, expected_type
):
    # Act
    await rapyer_key_model.asave()
    loaded = await RapyerKeyFieldModel.aget(rapyer_key_model.key)

    # Assert
    loaded_value = getattr(loaded, field_name)
    assert isinstance(loaded_value, expected_type)
    items = loaded_value.values() if isinstance(loaded_value, dict) else loaded_value
    assert all(isinstance(v, RapyerKey) for v in items)


@pytest.mark.asyncio
async def test_rapyer_key_field_model__save_and_get__data_persisted(
    real_redis_client, rapyer_key_model
):
    # Act
    await rapyer_key_model.asave()
    loaded = await RapyerKeyFieldModel.aget(rapyer_key_model.key)

    # Assert - values round-trip correctly with correct types
    assert loaded.single_key == "SomeModel:123"
    assert isinstance(loaded.single_key, RapyerKey)
    assert loaded.key_list == ["ModelA:1", "ModelA:2"]
    assert all(isinstance(k, RapyerKey) for k in loaded.key_list)
    assert loaded.key_dict == {"ref1": "ModelB:10", "ref2": "ModelB:20"}
    assert all(isinstance(v, RapyerKey) for v in loaded.key_dict.values())
    assert loaded.plain_key_list == ["ModelC:1", "ModelC:2"]
    assert all(isinstance(k, RapyerKey) for k in loaded.plain_key_list)
    assert loaded.plain_key_dict == {"ref1": "ModelD:10", "ref2": "ModelD:20"}
    assert all(isinstance(v, RapyerKey) for v in loaded.plain_key_dict.values())

    # Assert - raw Redis storage is plain strings, not pickle
    raw = (await real_redis_client.json().get(rapyer_key_model.key, "$"))[0]
    assert raw["single_key"] == "SomeModel:123"
    assert raw["key_list"] == ["ModelA:1", "ModelA:2"]
    assert raw["key_dict"] == {"ref1": "ModelB:10", "ref2": "ModelB:20"}
    assert raw["plain_key_list"] == ["ModelC:1", "ModelC:2"]
    assert raw["plain_key_dict"] == {"ref1": "ModelD:10", "ref2": "ModelD:20"}


@pytest.mark.asyncio
async def test_list_of_dicts_rapyer_key__save_and_get__items_are_rapyer_keys(
    real_redis_client,
):
    # Arrange
    model = ListOfDictsRapyerKeyModel(
        items=[
            {"a": RapyerKey("ModelA:1"), "b": RapyerKey("ModelA:2")},
            {"c": RapyerKey("ModelB:3")},
        ]
    )

    # Act
    await model.asave()
    loaded = await ListOfDictsRapyerKeyModel.aget(model.key)

    # Assert
    assert loaded.items == [{"a": "ModelA:1", "b": "ModelA:2"}, {"c": "ModelB:3"}]
    assert all(isinstance(v, RapyerKey) for d in loaded.items for v in d.values())
    raw = (await real_redis_client.json().get(model.key, "$"))[0]
    assert raw["items"] == [{"a": "ModelA:1", "b": "ModelA:2"}, {"c": "ModelB:3"}]


@pytest.mark.asyncio
async def test_dict_of_lists_rapyer_key__save_and_get__items_are_rapyer_keys(
    real_redis_client,
):
    # Arrange
    model = DictOfListsRapyerKeyModel(
        items={
            "group1": [RapyerKey("ModelA:1"), RapyerKey("ModelA:2")],
            "group2": [RapyerKey("ModelB:3")],
        }
    )

    # Act
    await model.asave()
    loaded = await DictOfListsRapyerKeyModel.aget(model.key)

    # Assert
    assert loaded.items == {
        "group1": ["ModelA:1", "ModelA:2"],
        "group2": ["ModelB:3"],
    }
    assert all(isinstance(v, RapyerKey) for lst in loaded.items.values() for v in lst)
    raw = (await real_redis_client.json().get(model.key, "$"))[0]
    assert raw["items"] == {
        "group1": ["ModelA:1", "ModelA:2"],
        "group2": ["ModelB:3"],
    }
