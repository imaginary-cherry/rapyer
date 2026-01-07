import dataclasses
from typing import TYPE_CHECKING, Annotated, Any, Generic, TypeAlias, TypeVar


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
