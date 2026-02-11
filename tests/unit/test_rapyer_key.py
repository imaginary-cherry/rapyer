import pytest

from rapyer.fields.key import RapyerKey
from tests.models.common import UserWithKeyModel
from tests.models.simple_types import StrModel


@pytest.mark.parametrize(
    ["model_class", "kwargs"],
    [
        [StrModel, {"name": "test"}],
        [UserWithKeyModel, {"user_id": "abc", "name": "Test", "email": "t@t.com"}],
    ],
)
def test_key_property_returns_rapyer_key(model_class, kwargs):
    # Arrange
    model = model_class(**kwargs)

    # Act
    key = model.key

    # Assert
    assert isinstance(key, RapyerKey)
    assert isinstance(key, str)


def test_rapyer_key_behaves_like_str():
    # Arrange
    key = RapyerKey("MyModel:123")

    # Act & Assert
    assert key == "MyModel:123"
    assert "MyModel" in key
    assert key.split(":") == ["MyModel", "123"]
