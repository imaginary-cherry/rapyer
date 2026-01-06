from tests.models.pickle_types import NonRedisDumpableModel
from tests.models.unit_types import SimpleBytesModel


def test_model_dump_with_unsupported_redis_types_sanity():
    # Arrange
    model = NonRedisDumpableModel(set_field={"1"})

    # Act
    result = model.model_dump(mode="json")

    # Assert
    assert result["set_field"] == ["1"]


def test_model_dump_with_byte_model_sanity():
    # Arrange
    byt = b"hello this is great"
    model = SimpleBytesModel(data=byt)

    # Act
    result = model.model_dump(mode="json")

    # Assert
    assert result["data"] == byt.decode("utf-8")
