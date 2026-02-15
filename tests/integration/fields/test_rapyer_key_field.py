import pytest

from rapyer.fields import RapyerKey
from tests.models.redis_types import RapyerKeyFieldModel


@pytest.mark.asyncio
async def test_rapyer_key_field_model__save_and_get__data_persisted(real_redis_client):
    # Arrange
    model = RapyerKeyFieldModel(
        single_key=RapyerKey("SomeModel:123"),
        key_list=[RapyerKey("ModelA:1"), RapyerKey("ModelA:2")],
        key_dict={"ref1": RapyerKey("ModelB:10"), "ref2": RapyerKey("ModelB:20")},
    )

    # Act
    await model.asave()
    loaded = await RapyerKeyFieldModel.aget(model.key)

    # Assert - values round-trip correctly with correct types
    assert loaded.single_key == "SomeModel:123"
    assert isinstance(loaded.single_key, RapyerKey)
    assert loaded.key_list == ["ModelA:1", "ModelA:2"]
    assert all(isinstance(k, RapyerKey) for k in loaded.key_list)
    assert loaded.key_dict == {"ref1": "ModelB:10", "ref2": "ModelB:20"}
    assert all(isinstance(v, RapyerKey) for v in loaded.key_dict.values())

    # Assert - raw Redis storage is plain strings, not pickle
    raw = (await real_redis_client.json().get(model.key, "$"))[0]
    assert raw["single_key"] == "SomeModel:123"
    assert raw["key_list"] == ["ModelA:1", "ModelA:2"]
    assert raw["key_dict"] == {"ref1": "ModelB:10", "ref2": "ModelB:20"}
