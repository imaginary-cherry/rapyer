from __future__ import annotations

import dataclasses
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
from rapyer.errors import (
    InvalidRefreshTtlError,
    MetaFrozenError,
    UnsupportedArgumentValueError,
)

DEFAULT_CONNECTION = "redis://localhost:6379/0"


@dataclasses.dataclass(frozen=True)
class WritePolicy:
    """
    Governs who may write a RedisConfig field and when.
    """

    # Writable even while Meta is frozen, for values rapyer itself derives.
    frozen_exempt: bool = False
    # init_rapyer() may fill this in when the user did not set it explicitly.
    resolvable: bool = False

    def check_write(self, config: "RedisConfig", name: str):
        if config._meta_locked and not self.frozen_exempt:
            raise MetaFrozenError(self.frozen_message(name))

    def check_resolvable(self, config: "RedisConfig", name: str):
        if name not in type(config).model_fields:
            raise UnsupportedArgumentValueError(f"Meta has no field named {name!r}.")
        if not self.resolvable:
            raise UnsupportedArgumentValueError(
                f"Meta.{name} is not a resolvable field; annotate it with "
                f"WritePolicy(resolvable=True) to allow init-time resolution."
            )

    def resolve(self, config: "RedisConfig", name: str, value: Any):
        self.check_resolvable(config, name)
        self.check_write(config, name)
        # Bypassing pydantic keeps the field out of model_fields_set, so it stays "not preset".
        object.__setattr__(config, name, value)

    @staticmethod
    def frozen_message(name: str) -> str:
        return (
            f"Meta.{name} is frozen after init_rapyer() bakes the config "
            f"into the cascade plan — call init_rapyer() again to "
            f"reconfigure instead of mutating Meta.{name} directly."
        )


# A field with no annotation gets the strictest policy, so new fields are guarded by default.
DEFAULT_WRITE_POLICY = WritePolicy()


def policy_for(config_cls: type[BaseModel], name: str) -> WritePolicy:
    field = config_cls.model_fields.get(name)
    if field is not None:
        for meta in field.metadata:
            if isinstance(meta, WritePolicy):
                return meta
    return DEFAULT_WRITE_POLICY


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
    cascade_function_name: Annotated[str | None, WritePolicy(frozen_exempt=True)] = None
    # Per-model vectorizer; None falls back to the packaged default, unlike cascade_ttl.
    vectorizer: Annotated[
        EmbeddingAdapter | None, SkipValidation, WritePolicy(resolvable=True)
    ] = None
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

    @model_validator(mode="after")
    def _build_redis_json(self):
        self._redis_json = self.redis.json()
        return self

    @property
    def redis_json(self):
        return self._redis_json

    @model_validator(mode="wrap")
    @classmethod
    def _enforce_write_policy(cls, data, handler, info):
        # Fires per assignment, so a missing annotation cannot lose the guard.
        if info.field_name is not None:
            policy_for(cls, info.field_name).check_write(data, info.field_name)
        return handler(data)

    def resolve_vectorizer(self, value: EmbeddingAdapter):
        """
        Fill the vectorizer when the user did not set one themselves.
        """
        field = "vectorizer"
        if not self.is_preset(field):
            policy_for(type(self), field).resolve(self, field, value)

    def is_preset(self, name: str) -> bool:
        if name not in type(self).model_fields:
            raise UnsupportedArgumentValueError(f"Meta has no field named {name!r}.")
        return name in self.model_fields_set

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
