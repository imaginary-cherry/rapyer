from datetime import datetime, timezone

import pytest
from rapyer.types.datetime import RedisDatetime, RedisDatetimeTimestamp


@pytest.mark.parametrize(
    ["year", "month", "day", "hour", "minute", "second"],
    [
        [2024, 1, 15, 10, 30, 45],
        [2023, 12, 31, 23, 59, 59],
        [2000, 6, 15, 0, 0, 0],
    ],
)
def test_redis_datetime_new_with_year_args_sanity(
    year, month, day, hour, minute, second
):
    # Arrange & Act
    result = RedisDatetime(year, month, day, hour, minute, second)

    # Assert
    assert isinstance(result, RedisDatetime)
    assert result.year == year
    assert result.month == month
    assert result.day == day
    assert result.hour == hour
    assert result.minute == minute
    assert result.second == second


@pytest.mark.parametrize(
    ["dt"],
    [
        [datetime(2024, 1, 15, 10, 30, 45)],
        [datetime(2023, 12, 31, 23, 59, 59, 123456)],
        [datetime(2000, 6, 15, 12, 0, 0, tzinfo=timezone.utc)],
    ],
)
def test_redis_datetime_new_with_datetime_instance_sanity(dt):
    # Arrange & Act
    result = RedisDatetime(dt)

    # Assert
    assert isinstance(result, RedisDatetime)
    assert result.year == dt.year
    assert result.month == dt.month
    assert result.day == dt.day
    assert result.hour == dt.hour
    assert result.minute == dt.minute
    assert result.second == dt.second
    assert result.microsecond == dt.microsecond
    assert result.tzinfo == dt.tzinfo


@pytest.mark.parametrize(
    ["invalid_value"],
    [
        [1],
        ["string"],
        [None],
        [datetime(2024, 1, 1)],
        [[1, 2, 3]],
    ],
)
def test_redis_datetime_iadd_raises_error_for_non_timedelta(invalid_value):
    # Arrange
    dt = RedisDatetime(2024, 1, 15, 10, 30, 45)

    # Act & Assert
    with pytest.raises(TypeError):
        dt += invalid_value


@pytest.mark.parametrize(
    ["invalid_value"],
    [
        [1],
        ["string"],
        [1.5],
        [[1, 2, 3]],
    ],
)
def test_redis_datetime_isub_raises_error_for_non_timedelta(invalid_value):
    # Arrange
    dt = RedisDatetime(2024, 1, 15, 10, 30, 45)

    # Act & Assert
    with pytest.raises(TypeError):
        dt -= invalid_value


@pytest.mark.parametrize(
    ["invalid_value"],
    [
        [1],
        ["string"],
        [1.5],
        [None],
        [datetime(2024, 1, 1)],
    ],
)
def test_redis_datetime_timestamp_iadd_raises_error_for_non_timedelta(invalid_value):
    # Arrange
    dt = RedisDatetimeTimestamp(2024, 1, 15, 10, 30, 45)

    # Act & Assert
    with pytest.raises(TypeError):
        dt += invalid_value


@pytest.mark.parametrize(
    ["invalid_value"],
    [
        [1],
        ["string"],
        [None],
        [[1, 2, 3]],
    ],
)
def test_redis_datetime_timestamp_isub_raises_error_for_non_timedelta(invalid_value):
    # Arrange
    dt = RedisDatetimeTimestamp(2024, 1, 15, 10, 30, 45)

    # Act & Assert
    with pytest.raises(TypeError):
        dt -= invalid_value
