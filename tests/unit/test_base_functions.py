from enum import Enum
from typing import Generic, TypeVar, Any

import pytest
from rapyer import AtomicRedisModel
from rapyer.base import find_redis_models, REDIS_MODELS


@pytest.fixture
def reset_redis_model_lst():
    original = REDIS_MODELS.copy()
    REDIS_MODELS.clear()
    yield
    REDIS_MODELS.clear()
    REDIS_MODELS.extend(original)


T = TypeVar("T")


def test_find_redis_models_returns_all_loaded_models_sanity(reset_redis_model_lst):
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
        GenericModel,
        GenericModel[type],
        GenericModel[Model],
    }

    # Act
    models = find_redis_models()

    # Assert
    assert set(models) == expected
