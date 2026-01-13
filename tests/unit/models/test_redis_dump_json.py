from datetime import datetime

from rapyer.types.base import REDIS_DUMP_FLAG_NAME
from tests.models.functionality_types import AllTypesModel, MyTestEnum


def test_redis_dump_json_load_with_context_many_types_sanity():
    # Arrange
    model = AllTypesModel(
        str_field="test_string",
        int_field=42,
        bool_field=True,
        datetime_field=datetime(2024, 6, 15, 12, 30, 45),
        bytes_field=b"test_bytes",
        any_field="any_value",
        enum_field=MyTestEnum.OPTION_B,
        list_field=["item1", "item2", "item3"],
        dict_field={"key1": "value1", "key2": "value2"},
    )

    # Act
    json_str = model.redis_dump_json()
    loaded_model = AllTypesModel.model_validate_json(
        json_str, context={REDIS_DUMP_FLAG_NAME: True}
    )

    # Assert
    assert loaded_model == model
