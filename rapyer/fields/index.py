import dataclasses
from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Any, Generic, TypeAlias, TypeVar

from rapyer.types.datetime import RedisDatetimeTimestamp


@dataclasses.dataclass(frozen=True)
class IndexAnnotation:
    pass


T = TypeVar("T")


class _IndexType(Generic[T]):
    def __new__(cls, typ: Any = None):
        if typ is None:
            return IndexAnnotation()

        # For datetime objects, use RedisDatetimeTimestamp instead of RedisDatetime
        if typ is datetime:
            typ = RedisDatetimeTimestamp

        return Annotated[typ, IndexAnnotation()]

    def __class_getitem__(cls, item):
        # For datetime objects, use RedisDatetimeTimestamp instead of RedisDatetime
        if item is datetime:
            item = RedisDatetimeTimestamp

        return Annotated[item, IndexAnnotation()]


Index = _IndexType


if TYPE_CHECKING:
    Index: TypeAlias = Annotated[T, IndexAnnotation()]  # pragma: no cover
