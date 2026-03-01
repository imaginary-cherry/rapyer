from enum import Enum
from typing import Any, ClassVar

from pydantic import GetCoreSchemaHandler, BaseModel, ConfigDict, Field
from pydantic_core import core_schema

from rapyer.base import AtomicRedisModel
from rapyer.config import RedisConfig


class StrStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"


class IntPriority(int, Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class PlainEnum(Enum):
    A = "a"
    B = "b"


class ModelWithStrEnumDefault(AtomicRedisModel):
    Meta: ClassVar[RedisConfig] = RedisConfig(prefer_normal_json_dump=True)
    status: StrStatus = StrStatus.ACTIVE
    name: str = "test"


class ModelWithIntEnumDefault(AtomicRedisModel):
    Meta: ClassVar[RedisConfig] = RedisConfig(prefer_normal_json_dump=True)
    priority: IntPriority = Field(default=IntPriority.LOW)
    name: str = "test"


class ModelWithEnumCreatedByFactory(AtomicRedisModel):
    status: PlainEnum = Field(default_factory=lambda: PlainEnum.A)


class ModelWithStrEnumInList(AtomicRedisModel):
    Meta: ClassVar[RedisConfig] = RedisConfig(prefer_normal_json_dump=True)
    statuses: list[StrStatus] = Field(default_factory=list)
    name: str = "test"


class ModelWithStrEnumInDict(AtomicRedisModel):
    Meta: ClassVar[RedisConfig] = RedisConfig(prefer_normal_json_dump=True)
    status_map: dict[str, StrStatus] = {}
    name: str = "test"


class InnerModelWithEnum(BaseModel):
    status: StrStatus = StrStatus.ACTIVE


class ModelWithNestedEnum(AtomicRedisModel):
    inner: InnerModelWithEnum = Field(default_factory=InnerModelWithEnum)
    name: str = "test"


class CustomSerializableType:
    """A custom type that implements Pydantic serialization."""

    def __init__(self, value: str, metadata: dict = None):  # type: ignore[assignment]
        self.value = value
        self.metadata = metadata or {}

    def __eq__(self, other):
        if not isinstance(other, CustomSerializableType):
            return False
        return self.value == other.value and self.metadata == other.metadata

    def __repr__(self):
        return f"CustomSerializableType(value='{self.value}', metadata={self.metadata})"

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        def validate_instance(value) -> "CustomSerializableType":
            if isinstance(value, cls):
                return value
            elif isinstance(value, dict):
                if "value" not in value:
                    raise ValueError("Missing required field 'value'")
                return cls(value=value["value"], metadata=value.get("metadata", {}))
            elif isinstance(value, str):
                return cls(value=value)
            else:
                raise ValueError(
                    f"Expected {cls.__name__}, dict, or str, got {type(value)}"
                )

        def serialize_instance(instance: "CustomSerializableType") -> dict:
            return {"value": instance.value, "metadata": instance.metadata}

        return core_schema.with_info_plain_validator_function(
            lambda v, _: validate_instance(v),
            serialization=core_schema.plain_serializer_function_ser_schema(
                serialize_instance,
                return_schema=core_schema.dict_schema(),
            ),
        )


class ComplexCustomType:
    """A more complex custom type with nested data."""

    def __init__(self, name: str, items: list[str], config: dict[str, int]):
        self.name = name
        self.items = items
        self.config = config

    def __eq__(self, other):
        if not isinstance(other, ComplexCustomType):
            return False
        return (
            self.name == other.name
            and self.items == other.items
            and self.config == other.config
        )

    def __repr__(self):
        return f"ComplexCustomType(name='{self.name}', items={self.items}, config={self.config})"

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        def validate_instance(value) -> "ComplexCustomType":
            if isinstance(value, cls):
                return value
            elif isinstance(value, dict):
                required_fields = ["name", "items", "config"]
                for field in required_fields:
                    if field not in value:
                        raise ValueError(f"Missing required field '{field}'")
                return cls(
                    name=value["name"], items=value["items"], config=value["config"]
                )
            else:
                raise ValueError(f"Expected {cls.__name__} or dict, got {type(value)}")

        def serialize_instance(instance: "ComplexCustomType") -> dict:
            return {
                "name": instance.name,
                "items": instance.items,
                "config": instance.config,
            }

        return core_schema.with_info_plain_validator_function(
            lambda v, _: validate_instance(v),
            serialization=core_schema.plain_serializer_function_ser_schema(
                serialize_instance,
                return_schema=core_schema.dict_schema(),
            ),
        )


class NestedPydanticModel(BaseModel):
    """A Pydantic model to test nested serialization."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    title: str
    count: int
    active: bool = True


class ModelWithCustomTypes(AtomicRedisModel):
    """Model that uses custom serializable types."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    simple_custom: CustomSerializableType
    complex_custom: ComplexCustomType
    pydantic_nested: NestedPydanticModel


class ModelWithPreferJsonDumpConfig(AtomicRedisModel):
    Meta: ClassVar[RedisConfig] = RedisConfig(prefer_normal_json_dump=True)
    status: StrStatus = StrStatus.ACTIVE
    name: str = "test"
