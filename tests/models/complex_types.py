from typing import Any

from pydantic import Field, BaseModel
from rapyer.base import AtomicRedisModel
from rapyer.fields.safe_load import SafeLoad


class NestedListModel(AtomicRedisModel):
    nested_list: list[list[str]]


class NestedDictModel(AtomicRedisModel):
    nested_dict: dict[str, dict[str, str]]


class ListOfDictsModel(AtomicRedisModel):
    list_of_dicts: list[dict[str, str]]


class DictOfListsModel(AtomicRedisModel):
    dict_of_lists: dict[str, list[str]]


class ComplexNestedModel(AtomicRedisModel):
    nested_list: list[list[str]]
    nested_dict: dict[str, dict[str, str]]
    list_of_dicts: list[dict[str, str]]
    dict_of_lists: dict[str, list[str]]


class TripleNestedModel(AtomicRedisModel):
    triple_list: list[list[list[str]]] = Field(default_factory=list)
    triple_dict: dict[str, dict[str, dict[str, str]]] = Field(default_factory=dict)


class InnerMostModel(BaseModel):
    lst: list[str] = Field(default_factory=list)
    counter: int = 0


class MiddleModel(BaseModel):
    inner_model: InnerMostModel = Field(default_factory=InnerMostModel)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class OuterModel(AtomicRedisModel):
    middle_model: MiddleModel = Field(default_factory=MiddleModel)
    user_data: dict[str, int] = Field(default_factory=dict)
    items: list[int] = Field(default_factory=list)


class InnerRedisModel(AtomicRedisModel):
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    counter: int = 0
    safe_data: SafeLoad[list[Any]] = Field(default_factory=list)


class ContainerModel(BaseModel):
    inner_redis: InnerRedisModel = Field(default_factory=InnerRedisModel)
    description: str = "default"


class OuterModelWithRedisNested(AtomicRedisModel):
    container: ContainerModel = Field(default_factory=ContainerModel)
    outer_data: list[int] = Field(default_factory=list)


class DuplicateInnerMostModel(BaseModel):
    names: list[str] = Field(default_factory=list)
    scores: dict[str, int] = Field(default_factory=dict)
    counter: int = 0


class DuplicateMiddleModel(BaseModel):
    inner_model: DuplicateInnerMostModel = Field(
        default_factory=DuplicateInnerMostModel
    )
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class TestRedisModel(AtomicRedisModel):
    middle_model: DuplicateMiddleModel = Field(default_factory=DuplicateMiddleModel)
    user_data: dict[str, int] = Field(default_factory=dict)
    items: list[int] = Field(default_factory=list)
    description: str = "test_model"
