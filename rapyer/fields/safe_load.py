import dataclasses
from typing import TYPE_CHECKING, Annotated, Any, Generic, TypeAlias, TypeVar


@dataclasses.dataclass(frozen=True)
class SafeLoadAnnotation:
    pass


T = TypeVar("T")


class _SafeLoadType(Generic[T]):
    def __new__(cls, typ: Any = None):
        if typ is None:
            return SafeLoadAnnotation()
        return Annotated[typ, SafeLoadAnnotation()]

    def __class_getitem__(cls, item):
        return Annotated[item, SafeLoadAnnotation()]


SafeLoad = _SafeLoadType


if TYPE_CHECKING:
    SafeLoad: TypeAlias = Annotated[T, SafeLoadAnnotation()]  # pragma: no cover
