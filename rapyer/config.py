from __future__ import annotations

from typing import Annotated, Union

import redis
from pydantic import BaseModel, ConfigDict, Field, SkipValidation, field_validator
from redis.asyncio import Redis

from rapyer.actions import ActionGroup
from rapyer.errors import InvalidRefreshTtlError

DEFAULT_CONNECTION = "redis://localhost:6379/0"


def create_all_types():
    from rapyer.types.init import ALL_TYPES

    return ALL_TYPES


class RedisConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, validate_assignment=True)

    # SkipValidation lets tests inject MagicMock/FakeRedis without a type error
    # while keeping the annotation for static analysis.
    redis: Annotated[Redis, SkipValidation] = Field(
        default_factory=lambda: redis.asyncio.from_url(
            DEFAULT_CONNECTION, decode_responses=True
        )
    )
    redis_type: dict[type, type] = Field(default_factory=create_all_types)
    ttl: int | None = None
    init_with_rapyer: bool = True
    # Enable TTL refresh on read/write operations by default.
    # Accepts bool (True=all actions, False=none) or ActionGroup flag set for fine-grained control.
    refresh_ttl: Union[bool, ActionGroup] = True
    # If True, all non-Redis-supported fields are treated as SafeLoad
    safe_load_all: bool = False
    # If True, use JSON serialization for fields that support it instead of pickle
    prefer_normal_json_dump: bool = False
    # Set to True when using FakeRedis to normalize JSON responses
    is_fake_redis: bool = False
    # Maximum number of keys to delete per pipeline transaction in adelete_many
    max_delete_per_transaction: int | None = 1000

    @field_validator("refresh_ttl", mode="after")
    @classmethod
    def _no_delete_in_refresh_ttl(
        cls, value: Union[bool, ActionGroup]
    ) -> Union[bool, ActionGroup]:
        if isinstance(value, ActionGroup) and (value & ActionGroup.DELETE):
            raise InvalidRefreshTtlError(
                "refresh_ttl cannot include ActionGroup.DELETE: the key is "
                "removed from Redis on delete, so TTL cannot be refreshed."
            )
        return value
