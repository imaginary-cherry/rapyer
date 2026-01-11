from datetime import datetime

import pytest
from pydantic import TypeAdapter
from rapyer.types.base import REDIS_DUMP_FLAG_NAME
from tests.models.unit_types import DatetimeTimestampModel


@pytest.mark.parametrize(
    ["test_datetime"],
    [
        [datetime(2023, 1, 1, 12, 0, 0)],
        [datetime(2024, 6, 15, 8, 30, 45)],
        [datetime(2025, 12, 31, 23, 59, 59)],
    ],
)
def test_redis_datetime_timestamp_normal_dump_sanity(test_datetime):
    # Arrange
    model = DatetimeTimestampModel(created_at=test_datetime)
    adapter = TypeAdapter(DatetimeTimestampModel)
    expected_iso_string = test_datetime.isoformat()

    # Act
    result = adapter.dump_python(model, mode="json")

    # Assert
    assert result["created_at"] == expected_iso_string
    assert isinstance(result["created_at"], str)


@pytest.mark.parametrize(
    ["test_datetime"],
    [
        [datetime(2023, 1, 1, 12, 0, 0)],
        [datetime(2024, 6, 15, 8, 30, 45)],
        [datetime(2025, 12, 31, 23, 59, 59)],
    ],
)
def test_redis_datetime_timestamp_redis_dump_sanity(test_datetime):
    # Arrange
    model = DatetimeTimestampModel(created_at=test_datetime)
    adapter = TypeAdapter(DatetimeTimestampModel)
    expected_timestamp = test_datetime.timestamp()

    # Act
    result = adapter.dump_python(
        model, mode="json", context={REDIS_DUMP_FLAG_NAME: True}
    )

    # Assert
    assert result["created_at"] == expected_timestamp
    assert isinstance(result["created_at"], float)
