"""D-15: mutating a RedisText field inside alock(save_at_end=True) holds a non-expiring lock across asave()'s embedding call - an accepted lock-hold-time cost, not guarded here."""

import base64
import json
from typing import Optional

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema

from rapyer.errors import (
    RedisTextEmbeddingNotMaterializedError,
    RedisTextRealRedisRequiredError,
)
from rapyer.types.base import REDIS_DUMP_FLAG_NAME
from rapyer.types.special import SpecialFieldType


class RedisText(str, SpecialFieldType):

    LUA_SNIPPET_DIR = "redis_text"

    def clone(self):
        return self.__class__(str(self))

    def pending_embed_text(self) -> Optional[str]:
        baseline = getattr(self, "_baseline_text", None)
        return str(self) if str(self) != baseline else None

    async def aprepare_special(self) -> None:
        vector_blob = getattr(self, "_prepared_vector", None)
        if vector_blob is None:
            return
        self._pending_embedding = vector_blob
        self._baseline_text = str(self)
        self._prepared_vector = None

    async def asave_special(self):
        if self.Meta.is_fake_redis:
            raise RedisTextRealRedisRequiredError(
                self._base_model_link.__class__.__name__
            )
        baseline = getattr(self, "_baseline_text", None)
        pending = getattr(self, "_pending_embedding", None)
        dirty = str(self) != baseline
        if dirty and pending is None:
            raise RedisTextEmbeddingNotMaterializedError(self.field_path)
        mapping = {
            "text": str(self),
            "parent": self.key,
            "field": self.field_path.lstrip("."),
        }
        if pending is not None:
            mapping["embedding"] = pending
            mapping["model_label"] = self.Meta.vectorizer.label
        await self.client.hset(self.special_key, mapping=mapping)
        self._pending_embedding = None

    async def adelete_special(self):
        await self.client.delete(self.special_key)

    async def aduplicate_special(self, target_special_key: str, target_model_key: str):
        # Follow-up HSET rewrites parent/field after COPY (D-17): plain COPY would keep the source's.
        await self.client.copy(self.special_key, target_special_key)
        await self.client.hset(
            target_special_key,
            mapping={
                "parent": target_model_key,
                "field": self.field_path.lstrip("."),
            },
        )

    def lua_save_payload(self) -> str:
        if self.Meta.is_fake_redis:
            raise RedisTextRealRedisRequiredError(
                self._base_model_link.__class__.__name__
            )
        pending = getattr(self, "_pending_embedding", None)
        if pending is None:
            raise RedisTextEmbeddingNotMaterializedError(self.field_path)
        return json.dumps(
            {
                "text": str(self),
                "embedding_b64": base64.b64encode(pending).decode("ascii"),
                "parent": self.key,
                "field": self.field_path.lstrip("."),
                "model_label": self.Meta.vectorizer.label,
            }
        )

    @classmethod
    def queue_special_loads_in_pipeline(
        cls, pipe, key: str, plan: list, parent_path: str = "", field_name: str = ""
    ):
        field_path = f"{parent_path}{field_name}"
        pipe.hget(cls.special_field_key(key, field_path), "text")
        plan.append([field_name.lstrip(".")])

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.with_info_after_validator_function(
            cls._finalize,
            handler(str),
            serialization=core_schema.plain_serializer_function_ser_schema(
                str, return_schema=core_schema.str_schema()
            ),
        )

    @classmethod
    def _finalize(cls, value, info):
        instance = cls(value)
        ctx = info.context or {}
        if ctx.get(REDIS_DUMP_FLAG_NAME):
            instance._baseline_text = value
        return instance
