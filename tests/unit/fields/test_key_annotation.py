from datetime import datetime

import pytest
from tests.models.common import UserWithKeyModel, EventWithDatetimeKeyModel


def test_key_field_name_detection_sanity():
    # Act & Assert
    assert UserWithKeyModel._key_field_name == "user_id"
    assert EventWithDatetimeKeyModel._key_field_name == "created_at"


@pytest.mark.parametrize(
    ["user_id"],
    [
        ["simple_id"],
        ["complex-id_with-symbols"],
        ["123456"],
        ["user@domain.com"],
    ],
)
def test_various_string_keys_included_in_key_sanity(user_id):
    # Arrange
    user = UserWithKeyModel(user_id=user_id, name="Test User", email="test@test.com")

    # Act & Assert
    assert user_id in user.key
    assert user.key == f"UserWithKeyModel:{user_id}"


@pytest.mark.parametrize(
    ["created_at"],
    [
        [datetime(2020, 1, 1, 0, 0, 0)],
        [datetime(2023, 12, 31, 23, 59, 59)],
        [datetime(2023, 6, 15, 12, 30, 45)],
    ],
)
def test_various_datetime_keys_included_in_key_sanity(created_at):
    # Arrange
    event = EventWithDatetimeKeyModel(
        created_at=created_at, event_name="Test Event", description="Test Description"
    )

    # Act & Assert
    assert str(created_at) in event.key
    assert event.key == f"EventWithDatetimeKeyModel:{created_at}"
