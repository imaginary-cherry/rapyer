from typing import TypeAlias, TYPE_CHECKING

from redis.commands.search.field import NumericField

from rapyer.scripts import run_sha, NUM_MUL_SCRIPT_NAME, NUM_TRUEDIV_SCRIPT_NAME
from rapyer.types.base import RedisType


class RedisFloat(float, RedisType):
    original_type = float

    @classmethod
    def redis_schema(cls, field_name: str):
        return NumericField(f"$.{field_name}", as_name=field_name)

    async def aincrease(self, amount: float = 1.0):
        result = await self.client.json().numincrby(self.key, self.json_path, amount)
        await self.refresh_ttl_if_needed()
        return result[0] if isinstance(result, list) and result else result

    def clone(self):
        return float(self)

    def __iadd__(self, other):
        new_value = self + other
        if self.pipeline:
            self.pipeline.json().numincrby(self.key, self.json_path, other)
        return self.__class__(new_value)

    def __isub__(self, other):
        new_value = self - other
        if self.pipeline:
            self.pipeline.json().numincrby(self.key, self.json_path, -other)
        return self.__class__(new_value)

    def __imul__(self, other):
        new_value = self * other
        if self.pipeline:
            run_sha(
                self.pipeline, NUM_MUL_SCRIPT_NAME, 1, self.key, self.json_path, other
            )
        return self.__class__(new_value)

    def __itruediv__(self, other):
        new_value = self / other
        if self.pipeline:
            run_sha(
                self.pipeline,
                NUM_TRUEDIV_SCRIPT_NAME,
                1,
                self.key,
                self.json_path,
                other,
            )
        return self.__class__(new_value)


if TYPE_CHECKING:
    RedisFloat: TypeAlias = RedisFloat | float  # pragma: no cover
