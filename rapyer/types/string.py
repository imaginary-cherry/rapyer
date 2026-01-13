from typing import TypeAlias, TYPE_CHECKING

from rapyer.types.base import RedisType


class RedisStr(str, RedisType):
    original_type = str

    def clone(self):
        return str(self)

    def __iadd__(self, other):
        new_value = self + other
        if self.pipeline:
            self.pipeline.json().set(self.key, self.json_path, new_value)
        return self.__class__(new_value)


if TYPE_CHECKING:
    RedisStr: TypeAlias = RedisStr | str  # pragma: no cover
