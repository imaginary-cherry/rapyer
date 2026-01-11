from typing import Generic, TypeVar

from pydantic import Field, BaseModel
from rapyer.base import AtomicRedisModel

T = TypeVar("T")


class GenericListModel(AtomicRedisModel, Generic[T]):
    items: list[T] = Field(default_factory=list)
    name: str = "generic_model"


class GenericDictModel(AtomicRedisModel, Generic[T]):
    data: dict[str, T] = Field(default_factory=dict)
    metadata: dict[str, str] = Field(default_factory=dict)


class GenericBaseModel(BaseModel, Generic[T]):
    value: T
    label: str = "default"


class CompositeGenericModel(AtomicRedisModel):
    base_field: GenericBaseModel[str]
    atomic_field: GenericListModel[int]
    complex_field: GenericListModel[GenericBaseModel[bytes]]
