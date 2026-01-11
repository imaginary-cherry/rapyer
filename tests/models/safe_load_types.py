from typing import Optional, Type, Any

from pydantic import Field

from rapyer.base import AtomicRedisModel
from rapyer.fields.safe_load import SafeLoad


class ModelWithSafeLoadField(AtomicRedisModel):
    safe_type_field: SafeLoad[Optional[Type[str]]] = Field(default=None)
    normal_field: str = Field(default="default")


class ModelWithMultipleSafeLoadFields(AtomicRedisModel):
    safe_field_1: SafeLoad[Optional[type]] = Field(default=None)
    safe_field_2: SafeLoad[Optional[Type[Any]]] = Field(default=None)
    normal_field: str = Field(default="default")


class ModelWithMixedFields(AtomicRedisModel):
    safe_field: SafeLoad[Optional[type]] = Field(default=None)
    unsafe_field: Optional[type] = Field(default=None)
    normal_field: str = Field(default="default")
