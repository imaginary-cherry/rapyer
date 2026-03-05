import dataclasses
from typing import Annotated, Any, Generic, TYPE_CHECKING, TypeAlias, TypeVar


@dataclasses.dataclass(frozen=True)
class KeyAnnotation:
    pass


T = TypeVar("T")


class _KeyType(Generic[T]):
    def __new__(cls, typ: Any = None):
        if typ is None:
            return KeyAnnotation()
        return Annotated[typ, KeyAnnotation()]

    def __class_getitem__(cls, item):
        return Annotated[item, KeyAnnotation()]


Key = _KeyType


if TYPE_CHECKING:
    Key: TypeAlias = Annotated[T, KeyAnnotation()]  # pragma: no cover


class RapyerKey(str):
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        from pydantic_core import core_schema

        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.str_schema(),
            serialization=core_schema.plain_serializer_function_ser_schema(str),
        )
