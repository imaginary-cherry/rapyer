from typing import TYPE_CHECKING, TypeAlias

from rapyer.actions import ActionGroup, mark_actions, marks_redis_updated
from rapyer.scripts import STR_APPEND_SCRIPT_NAME, STR_MUL_SCRIPT_NAME, run_sha
from rapyer.types.base import RedisType


class RedisStr(str, RedisType):
    def clone(self):
        return str(self)

    @marks_redis_updated
    @mark_actions(ActionGroup.UPDATE, ActionGroup.APPEND)
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

    @marks_redis_updated
    @mark_actions(ActionGroup.UPDATE)
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
    RedisStr: TypeAlias = RedisStr | str
