from enum import Enum
from typing import Any, Generic, TypeVar

import pytest

from rapyer import AtomicRedisModel
from rapyer.base import find_redis_models
from rapyer.config import RedisConfig
from rapyer.errors import DuplicateModelNameError, UnsupportedIndexedFieldError
from rapyer.fields import Index

T = TypeVar("T")


def test_find_redis_models_returns_all_loaded_models_sanity(clean_redis_models):
    # Arrange
    class Model(AtomicRedisModel):
        field1: list[str]
        field2: dict[str, str]

    class GenericModel(AtomicRedisModel, Generic[T]):
        field1: list[T]
        field2: Any

    class Model2(AtomicRedisModel):
        field1: Model
        field2: type
        field3: GenericModel[type]

    class E(str, Enum):
        VAL = "val"

    class Model3(AtomicRedisModel):
        field1: Model2
        field2: E

    class Model4(Model3):
        field3: GenericModel[Model]
        field2: list[GenericModel[Model]]

    expected = {
        Model,
        Model2,
        Model3,
        Model4,
        GenericModel[type],
        GenericModel[Model],
    }

    # Act
    models = find_redis_models()

    # Assert
    assert set(models) == expected
    # Generic model is not registered
    assert GenericModel not in models


def test_registering_two_models_with_same_class_name_raises(clean_redis_models):
    # Arrange
    class DuplicateNameModel(AtomicRedisModel):
        field1: str = ""

    # Act & Assert
    with pytest.raises(DuplicateModelNameError) as exc_info:

        class DuplicateNameModel(AtomicRedisModel):  # noqa: F811
            field2: int = 0

    assert exc_info.value.model_name == "DuplicateNameModel"


def test_redis_schema_raises_for_indexed_field_with_unsupported_scalar_type_sanity(
    clean_redis_models,
):
    # ``complex`` is a valid pydantic type but has no RedisType conversion, so its
    # annotation reaches redis_schema unconverted. With the Index flag set it is not
    # an AtomicRedisModel nor a RedisType, so it falls through to the final guard that
    # rejects indexed fields whose type Redis cannot index.
    class IndexedComplexModel(AtomicRedisModel):
        name: str
        value: Index[complex]

        Meta = RedisConfig(init_with_rapyer=False)

    # Act & Assert
    with pytest.raises(UnsupportedIndexedFieldError):
        IndexedComplexModel.redis_schema()
