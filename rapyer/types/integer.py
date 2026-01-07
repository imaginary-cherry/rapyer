from typing import TypeAlias, TYPE_CHECKING

from redis.commands.search.field import NumericField
from typing_extensions import deprecated

from rapyer.types.base import RedisType
from rapyer.utils.redis import refresh_ttl_if_needed


class RedisInt(int, RedisType):
    original_type = int

    @classmethod
    def redis_schema(cls, field_name: str):
        return NumericField(f"$.{field_name}", as_name=field_name)

    @deprecated(
        f"increase function is deprecated and will become sync function in rapyer 1.2.0, use aincrease() instead"
    )
    async def increase(self, amount: int = 1):
        return await self.aincrease(amount)

    async def aincrease(self, amount: int = 1):
        result = await self.client.json().numincrby(self.key, self.json_path, amount)
        await refresh_ttl_if_needed(
            self.client, self.key, self.Meta.ttl, self.Meta.refresh_ttl
        )
        return result[0] if isinstance(result, list) and result else result

    def clone(self):
        return int(self)

    def __iadd__(self, other):
        new_value = self + other
        if self.pipeline:
            self.pipeline.json().set(self.key, self.json_path, new_value)
        return self.__class__(new_value)

    def __isub__(self, other):
        new_value = self - other
        if self.pipeline:
            self.pipeline.json().set(self.key, self.json_path, new_value)
        return self.__class__(new_value)

    def __imul__(self, other):
        new_value = self * other
        if self.pipeline:
            self.pipeline.json().set(self.key, self.json_path, new_value)
        return self.__class__(new_value)

    def __ifloordiv__(self, other):
        new_value = self // other
        if self.pipeline:
            self.pipeline.json().set(self.key, self.json_path, new_value)
        return self.__class__(new_value)

    def __imod__(self, other):
        new_value = self % other
        if self.pipeline:
            self.pipeline.json().set(self.key, self.json_path, new_value)
        return self.__class__(new_value)

    def __ipow__(self, other):
        new_value = self**other
        if self.pipeline:
            self.pipeline.json().set(self.key, self.json_path, new_value)
        return self.__class__(new_value)


if TYPE_CHECKING:
    RedisInt: TypeAlias = RedisInt | int  # pragma: no cover
