from datetime import datetime
from typing import List, Dict, Any

from pydantic import Field
from rapyer.base import AtomicRedisModel
from tests.models.common import (
    Status,
    Person,
    User,
    Product,
    UserProfile,
    NestedConfig,
    Address,
    Company,
    Settings,
)


class SimpleListModel(AtomicRedisModel):
    items: list[str] = Field(default_factory=list)


class SimpleIntListModel(AtomicRedisModel):
    numbers: list[int] = Field(default_factory=list)


class SimpleDictModel(AtomicRedisModel):
    data: dict[str, str] = Field(default_factory=dict)


class ListModel(AtomicRedisModel):
    items: list[str] = Field(default_factory=list)
    numbers: list[int] = Field(default_factory=list)


class DictModel(AtomicRedisModel):
    data: dict[str, str] = Field(default_factory=dict)
    config: dict[str, int] = Field(default_factory=dict)


class MixedTypesModel(AtomicRedisModel):
    str_list: List[str] = Field(default_factory=list)
    bytes_list: List[bytes] = Field(default_factory=list)
    int_list: List[int] = Field(default_factory=list)
    bool_list: List[bool] = Field(default_factory=list)
    mixed_list: List[Any] = Field(default_factory=list)
    str_dict: Dict[str, str] = Field(default_factory=dict)
    bytes_dict: Dict[str, bytes] = Field(default_factory=dict)
    int_dict: Dict[str, int] = Field(default_factory=dict)
    bool_dict: Dict[str, bool] = Field(default_factory=dict)
    mixed_dict: Dict[str, Any] = Field(default_factory=dict)


class BaseDictMetadataModel(AtomicRedisModel):
    metadata: dict = Field(default_factory=dict)


class StrDictModel(BaseDictMetadataModel):
    metadata: dict[str, str] = Field(default_factory=dict)


class IntDictModel(BaseDictMetadataModel):
    metadata: dict[str, int] = Field(default_factory=dict)


class BytesDictModel(BaseDictMetadataModel):
    metadata: dict[str, bytes] = Field(default_factory=dict)


class DatetimeDictModel(BaseDictMetadataModel):
    metadata: dict[str, datetime] = Field(default_factory=dict)


class EnumDictModel(BaseDictMetadataModel):
    metadata: dict[str, Status] = Field(default_factory=dict)


class AnyDictModel(BaseDictMetadataModel):
    metadata: dict[str, Any] = Field(default_factory=dict)


class BaseModelDictModel(BaseDictMetadataModel):
    metadata: dict[str, Person] = Field(default_factory=dict)


class BoolDictModel(BaseDictMetadataModel):
    metadata: dict[str, bool] = Field(default_factory=dict)


class ListDictModel(BaseDictMetadataModel):
    metadata: dict[str, list[str]] = Field(default_factory=dict)


class NestedDictModel(BaseDictMetadataModel):
    metadata: dict[str, dict[str, str]] = Field(default_factory=dict)


class IntListModel(AtomicRedisModel):
    items: list[int] = Field(default_factory=list)


class StrListModel(AtomicRedisModel):
    items: list[str] = Field(default_factory=list)


class DictListModel(AtomicRedisModel):
    items: list[dict[str, str]] = Field(default_factory=list)


class BaseModelListModel(AtomicRedisModel):
    users: list[UserProfile] = Field(default_factory=list)
    products: list[Product] = Field(default_factory=list)
    configs: list[NestedConfig] = Field(default_factory=list)


class UserListModel(AtomicRedisModel):
    users: list[User] = Field(default_factory=list)


class ProductListModel(AtomicRedisModel):
    products: list[Product] = Field(default_factory=list)


class ComprehensiveTestModel(AtomicRedisModel):
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    name: str = ""
    counter: int = 0


class PipelineTestModel(AtomicRedisModel):
    metadata: dict[str, str] = Field(default_factory=dict)
    config: dict[str, int] = Field(default_factory=dict)


class DictDictModel(AtomicRedisModel):
    metadata: dict[str, dict[str, str]] = Field(default_factory=dict)


class BaseModelDictSetitemModel(AtomicRedisModel):
    addresses: dict[str, Address] = Field(default_factory=dict)
    companies: dict[str, Company] = Field(default_factory=dict)
    configs: dict[str, Settings] = Field(default_factory=dict)
