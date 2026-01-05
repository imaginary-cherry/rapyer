from typing import Type, Any, Optional

from pydantic import Field

from rapyer.base import AtomicRedisModel


class ModelWithUnserializableFields(AtomicRedisModel):
    model_type: Optional[Type[str]] = Field(default=str)
    callable_field: Optional[type] = Field(default=type)
    python_type: Optional[Type[Any]] = Field(default=int)
    value: Optional[int] = Field(default=42)


class DictPickableTypesModel(AtomicRedisModel):
    type_dict: dict[str, Type[str]] = Field(default_factory=dict)
    tuple_dict: dict[str, tuple[str, int]] = Field(default_factory=dict)
    set_dict: dict[str, set[str]] = Field(default_factory=dict)
    frozenset_dict: dict[str, frozenset[int]] = Field(default_factory=dict)


class ListPickableTypesModel(AtomicRedisModel):
    type_list: list[type] = Field(default_factory=list)
    tuple_list: list[tuple[str, int]] = Field(default_factory=list)
    set_list: list[set[str]] = Field(default_factory=list)
    frozenset_list: list[frozenset[int]] = Field(default_factory=list)
    nested_list: list[list[type]] = Field(default_factory=list)
