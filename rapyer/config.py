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
from rapyer.embeddings.protocol import EmbeddingAdapter
from rapyer.errors import InvalidRefreshTtlError, MetaFrozenError

DEFAULT_CONNECTION = "redis://localhost:6379/0"


def create_all_types():
    from rapyer.types.init import ALL_TYPES

    return ALL_TYPES


class RedisConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, validate_assignment=True)

    # SkipValidation lets tests inject MagicMock/FakeRedis without a pydantic type error.
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
    # Per-model vectorizer; None falls back to the packaged default (D-08), unlike cascade_ttl.
    vectorizer: Annotated[EmbeddingAdapter | None, SkipValidation] = None
    init_with_rapyer: bool = True
    # Enable TTL refresh by default; bool (all/none) or ActionGroup for fine-grained control.
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
    # True once init_rapyer() bakes the cascade plan; blocks mutation until re-init.
    _meta_locked: bool = PrivateAttr(default=False)
    # True once a user explicitly sets vectorizer; init_rapyer()'s own writes never set this.
    _vectorizer_preset: bool = PrivateAttr(default=False)

    @model_validator(mode="after")
    def _build_redis_json(self):
        self._redis_json = self.redis.json()
        self._vectorizer_preset = "vectorizer" in self.model_fields_set
        return self

    @property
    def redis_json(self):
        return self._redis_json

    def __setattr__(self, name: str, value: Any):
        # Frozen Meta blocks public field writes; private attrs stay writable for init/teardown.
        if (
            self._meta_locked
            and not name.startswith("_")
            # cascade_function_name is a derived value, writable even when frozen.
            and name != "cascade_function_name"
        ):
            raise MetaFrozenError(
                f"Meta.{name} is frozen after init_rapyer() bakes the config "
                f"into the cascade plan — call init_rapyer() again to "
                f"reconfigure instead of mutating Meta.{name} directly."
            )
        if name == "vectorizer":
            self._vectorizer_preset = True
        super().__setattr__(name, value)

    def _resolve_vectorizer(self, value: EmbeddingAdapter) -> None:
        # init_rapyer()'s internal-only write path; bypasses the preset-flagging hook above.
        if self._meta_locked:
            raise MetaFrozenError(
                "Meta.vectorizer is frozen after init_rapyer() bakes the config "
                "into the cascade plan — call init_rapyer() again to "
                "reconfigure instead of mutating Meta.vectorizer directly."
            )
        object.__setattr__(self, "vectorizer", value)

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
