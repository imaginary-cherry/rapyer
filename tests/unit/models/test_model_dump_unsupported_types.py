from tests.models.pickle_types import NonRedisDumpableModel


def test_model_dump_with_unsupported_redis_types_sanity():
    # Arrange
    model = NonRedisDumpableModel(set_field={"1"})

    # Act
    result = model.model_dump(mode="json")

    # Assert
    assert result["set_field"] == ["1"]
