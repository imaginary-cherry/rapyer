"""D-15: mutating a RedisText field inside alock(save_at_end=True) holds a non-expiring lock across asave()'s embedding call - an accepted lock-hold-time cost, not guarded here."""

import base64
import json
from collections import defaultdict
from typing import Any

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema

from rapyer.embeddings.adapter import pack_float32_blob
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

    @classmethod
    async def aprepare_many(cls, fields: list["RedisText"]) -> None:
        dirty = [f for f in fields if str(f) != getattr(f, "_baseline_text", None)]
        if not dirty:
            return
        # Sub-group by vectorizer identity: nested models may use a different vectorizer (D-08).
        groups: dict[int, list["RedisText"]] = defaultdict(list)
        vectorizers: dict[int, Any] = {}
        for field in dirty:
            vectorizer = field.Meta.vectorizer
            groups[id(vectorizer)].append(field)
            vectorizers[id(vectorizer)] = vectorizer
        for group_key, group_fields in groups.items():
            vectorizer = vectorizers[group_key]
            vectors = await vectorizer.aembed_many([str(f) for f in group_fields])
            for field, vector in zip(group_fields, vectors):
                field._pending_embedding = pack_float32_blob(vector, vectorizer.dims)
                field._baseline_text = str(field)

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
            "field": self.field_path.lstrip("."),
        }
        if pending is not None:
            mapping["embedding"] = pending
            mapping["model_label"] = self.Meta.vectorizer.label
        await self.client.hset(self.special_key, mapping=mapping)
        self._pending_embedding = None

    async def adelete_special(self):
        await self.client.delete(self.special_key)

    async def aduplicate_special(self, target_special_key: str):
        # Server-side COPY needs no follow-up rewrite: every field the HASH carries is either
        # content (text/embedding/model_label) or identical for the duplicate (`field` shares
        # the source's path). A COPY of an absent source is a no-op that creates nothing.
        await self.client.copy(self.special_key, target_special_key)

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
