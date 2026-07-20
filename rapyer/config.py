from __future__ import annotations

from typing import Annotated, Any, Union

import redis
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    SkipValidation,
    field_validator,
    model_validator,
)
from redis.asyncio import Redis
from redis.commands.json import JSON

from rapyer.actions import ActionGroup
from rapyer.cascade import CascadeTTL
from rapyer.errors import InvalidRefreshTtlError, MetaFrozenError

DEFAULT_CONNECTION = "redis://localhost:6379/0"


def create_all_types():
    from rapyer.types.init import ALL_TYPES

    return ALL_TYPES


class RedisConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, validate_assignment=True)

    # SkipValidation lets tests inject MagicMock/FakeRedis without a type error
    # while keeping the annotation for static analysis.
    redis: Annotated[
        Redis,
        SkipValidation,
        Field(
            default_factory=lambda: redis.asyncio.from_url(
                DEFAULT_CONNECTION, decode_responses=True
            )
        ),
    ]
    redis_type: dict[type, type] = Field(default_factory=create_all_types)
    ttl: int | None = None
    # Global TTL-cascade default, disabled unless init_rapyer(cascade_ttl=...) sets it.
    cascade_ttl: CascadeTTL | None = None
    # Plan-hashed cascade Redis Function name, init-baked (None on fakeredis).
    cascade_function_name: str | None = None
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

    _redis_json: JSON = PrivateAttr(default=None)
    # Set to True by init_rapyer() once the config is baked into the cascade
    # plan, refusing further mutation until the next init_rapyer() call.
    _meta_locked: bool = PrivateAttr(default=False)

    @model_validator(mode="after")
    def _build_redis_json(self):
        self._redis_json = self.redis.json()
        return self

    @property
    def redis_json(self):
        return self._redis_json

    def __setattr__(self, name: str, value: Any):
        # The whole config is baked into the cascade plan at init, so once frozen
        # no public field may change until the next init_rapyer(). Private attrs
        # (including _meta_locked itself) stay writable so init/teardown can
        # toggle it.
        # cascade_function_name is exempt: it is a DERIVED value (hash of the
        # already-frozen plan) that the cascade self-heal path (handle_missing_function)
        # rewrites at runtime, not a plan INPUT, so it must stay writable even when frozen.
        if (
            self._meta_locked
            and not name.startswith("_")
            and name != "cascade_function_name"
        ):
            raise MetaFrozenError(
                f"Meta.{name} is frozen after init_rapyer() bakes the config "
                f"into the cascade plan — call init_rapyer() again to "
                f"reconfigure instead of mutating Meta.{name} directly."
            )
        super().__setattr__(name, value)

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
