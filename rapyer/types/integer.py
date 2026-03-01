from typing import TypeAlias, TYPE_CHECKING

from redis.commands.search.field import NumericField

from rapyer.scripts import (
    run_sha,
    NUM_MUL_SCRIPT_NAME,
    NUM_FLOORDIV_SCRIPT_NAME,
    NUM_MOD_SCRIPT_NAME,
    NUM_POW_SCRIPT_NAME,
)
from rapyer.types.base import RedisType, marks_redis_updated


class RedisInt(int, RedisType):
    original_type = int

    @classmethod
    def redis_schema(cls, field_name: str):
        return NumericField(f"$.{field_name}", as_name=field_name)

    async def aincrease(self, amount: int = 1):
        result = await self.client.json().numincrby(self.key, self.json_path, amount)
        await self.refresh_ttl_if_needed()
        return result[0] if isinstance(result, list) and result else result

    def clone(self):
        return int(self)

    @marks_redis_updated
    def __iadd__(self, other):
        if self.pipeline:
            self.pipeline.json().numincrby(self.key, self.json_path, other)
        new_value = self + other
        return self.__class__(new_value)

    @marks_redis_updated
    def __isub__(self, other):
        if self.pipeline:
            self.pipeline.json().numincrby(self.key, self.json_path, -other)
        new_value = self - other
        return self.__class__(new_value)

    @marks_redis_updated
    def __imul__(self, other):
        new_value = self * other
        if self.pipeline:
            run_sha(
                self.pipeline, NUM_MUL_SCRIPT_NAME, 1, self.key, self.json_path, other
            )
        return self.__class__(new_value)

    @marks_redis_updated
    def __ifloordiv__(self, other):
        new_value = self // other
        if self.pipeline:
            run_sha(
                self.pipeline,
                NUM_FLOORDIV_SCRIPT_NAME,
                1,
                self.key,
                self.json_path,
                other,
            )
        return self.__class__(new_value)

    @marks_redis_updated
    def __imod__(self, other):
        new_value = self % other
        if self.pipeline:
            run_sha(
                self.pipeline, NUM_MOD_SCRIPT_NAME, 1, self.key, self.json_path, other
            )
        return self.__class__(new_value)

    @marks_redis_updated
    def __ipow__(self, other):
        new_value = self**other
        if self.pipeline:
            run_sha(
                self.pipeline, NUM_POW_SCRIPT_NAME, 1, self.key, self.json_path, other
            )
        return self.__class__(new_value)


if TYPE_CHECKING:
    RedisInt: TypeAlias = RedisInt | int  # pragma: no cover
