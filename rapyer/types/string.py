from typing import TypeAlias, TYPE_CHECKING

from rapyer.scripts import run_sha, STR_APPEND_SCRIPT_NAME, STR_MUL_SCRIPT_NAME
from rapyer.types.base import RedisType


class RedisStr(str, RedisType):
    original_type = str

    def clone(self):
        return str(self)

    def __iadd__(self, other):
        new_value = self + other
        if self.pipeline:
            run_sha(
                self.pipeline,
                STR_APPEND_SCRIPT_NAME,
                1,
                self.key,
                self.json_path,
                other,
            )
        return self.__class__(new_value)

    def __imul__(self, other):
        new_value = self * other
        if self.pipeline:
            run_sha(
                self.pipeline,
                STR_MUL_SCRIPT_NAME,
                1,
                self.key,
                self.json_path,
                other,
            )
        return self.__class__(new_value)


if TYPE_CHECKING:
    RedisStr: TypeAlias = RedisStr | str  # pragma: no cover
