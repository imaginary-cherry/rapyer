import asyncio
import base64
import contextlib
import functools
import pickle
import uuid
from contextlib import AbstractAsyncContextManager
from typing import ClassVar, Any, get_origin

from pydantic import (
    BaseModel,
    PrivateAttr,
    ConfigDict,
    model_validator,
    field_serializer,
    field_validator,
)
from pydantic_core.core_schema import FieldSerializationInfo, ValidationInfo
from redis.commands.search.index_definition import IndexDefinition, IndexType
from redis.commands.search.query import Query
from typing_extensions import deprecated

from rapyer.config import RedisConfig
from rapyer.context import _context_var, _context_xx_pipe
from rapyer.errors.base import KeyNotFound, UnsupportedIndexedFieldError
from rapyer.fields.expression import ExpressionField, AtomicField, Expression
from rapyer.fields.index import IndexAnnotation
from rapyer.fields.key import KeyAnnotation
from rapyer.links import REDIS_SUPPORTED_LINK
from rapyer.types.base import RedisType, REDIS_DUMP_FLAG_NAME
from rapyer.types.convert import RedisConverter
from rapyer.typing_support import Self, Unpack
from rapyer.utils.annotation import (
    replace_to_redis_types_in_annotation,
    has_annotation,
    field_with_flag,
    DYNAMIC_CLASS_DOC,
)
from rapyer.utils.fields import get_all_pydantic_annotation, is_redis_field
from rapyer.utils.pythonic import safe_issubclass
from rapyer.utils.redis import (
    acquire_lock,
    update_keys_in_pipeline,
    refresh_ttl_if_needed,
)


def make_pickle_field_serializer(field: str):
    @field_serializer(field, when_used="json-unless-none")
    def pickle_field_serializer(v, info: FieldSerializationInfo):
        ctx = info.context or {}
        should_serialize_redis = ctx.get(REDIS_DUMP_FLAG_NAME, False)
        if should_serialize_redis:
            return base64.b64encode(pickle.dumps(v)).decode("utf-8")
        return v

    pickle_field_serializer.__name__ = f"__serialize_{field}"

    @field_validator(field, mode="before")
    def pickle_field_validator(v, info: ValidationInfo):
        if v is None:
            return v
        ctx = info.context or {}
        should_serialize_redis = ctx.get(REDIS_DUMP_FLAG_NAME, False)
        if should_serialize_redis:
            return pickle.loads(base64.b64decode(v))
        return v

    pickle_field_validator.__name__ = f"__deserialize_{field}"

    return pickle_field_serializer, pickle_field_validator


class AtomicRedisModel(BaseModel):
    _pk: str = PrivateAttr(default_factory=lambda: str(uuid.uuid4()))
    _base_model_link: Self | RedisType = PrivateAttr(default=None)

    Meta: ClassVar[RedisConfig] = RedisConfig()
    _key_field_name: ClassVar[str | None] = None
    _field_name: str = PrivateAttr(default="")
    model_config = ConfigDict(validate_assignment=True, validate_default=True)

    @property
    def pk(self):
        if self._key_field_name:
            return self.model_dump(include={self._key_field_name})[self._key_field_name]
        return self._pk

    @pk.setter
    def pk(self, value: str):
        self._pk = value

    @property
    def field_name(self):
        return self._field_name

    @field_name.setter
    def field_name(self, value: str):
        self._field_name = value

    @property
    def field_path(self):
        if not self._base_model_link:
            return self.field_name
        parent_field_path = self._base_model_link.field_path
        if parent_field_path:
            return f"{parent_field_path}{self.field_name}"
        return self.field_name

    @property
    def json_path(self):
        field_path = self.field_path
        return f"${field_path}" if field_path else "$"

    @classmethod
    def redis_schema(cls, redis_name: str = ""):
        fields = []

        for field_name, field_info in cls.model_fields.items():
            real_type = field_info.annotation
            # Check if real_type is a class before using issubclass
            if get_origin(real_type) is not None or not isinstance(real_type, type):
                if field_with_flag(field_info, IndexAnnotation):
                    raise UnsupportedIndexedFieldError(
                        f"Field {field_name} is type {real_type}, and not supported for indexing"
                    )
                else:
                    continue

            full_redis_name = f"{redis_name}.{field_name}" if redis_name else field_name
            if issubclass(real_type, AtomicRedisModel):
                real_type: type[AtomicRedisModel]
                sub_fields = real_type.redis_schema(full_redis_name)
                fields.extend(sub_fields)
            elif not field_with_flag(field_info, IndexAnnotation):
                continue
            elif issubclass(real_type, RedisType):
                field_schema = real_type.redis_schema(full_redis_name)
                fields.append(field_schema)
            else:
                raise UnsupportedIndexedFieldError(
                    f"Indexed field {field_name} must be redis-supported to be indexed, see {REDIS_SUPPORTED_LINK}"
                )

        return fields

    @classmethod
    def index_name(cls):
        return f"idx:{cls.class_key_initials()}"

    @classmethod
    async def acreate_index(cls):
        fields = cls.redis_schema()
        if not fields:
            return
        await cls.Meta.redis.ft(cls.index_name()).create_index(
            fields,
            definition=IndexDefinition(
                prefix=[f"{cls.class_key_initials()}:"],
                index_type=IndexType.JSON,
            ),
        )

    @classmethod
    async def adelete_index(cls):
        await cls.Meta.redis.ft(cls.index_name()).dropindex(delete_documents=False)

    @classmethod
    def class_key_initials(cls):
        return cls.__name__

    @property
    def key_initials(self):
        return self.class_key_initials()

    @property
    def key(self):
        if self._base_model_link:
            return self._base_model_link.key
        return f"{self.key_initials}:{self.pk}"

    @key.setter
    def key(self, value: str):
        self._pk = value.split(":", maxsplit=1)[-1]

    def __init_subclass__(cls, **kwargs):
        # Find a field with KeyAnnotation and save its name
        for field_name, annotation in cls.__annotations__.items():
            if has_annotation(annotation, KeyAnnotation):
                cls._key_field_name = field_name
                break

        # Redefine annotations to use redis types
        pydantic_annotation = get_all_pydantic_annotation(cls, AtomicRedisModel)
        new_annotation = {
            field_name: field.annotation
            for field_name, field in pydantic_annotation.items()
        }
        original_annotations = cls.__annotations__.copy()
        original_annotations.update(new_annotation)
        new_annotations = {
            field_name: replace_to_redis_types_in_annotation(
                annotation, RedisConverter(cls.Meta.redis_type, f".{field_name}")
            )
            for field_name, annotation in original_annotations.items()
            if is_redis_field(field_name, annotation)
        }
        cls.__annotations__ = {**cls.__annotations__, **new_annotations}
        for field_name, field in pydantic_annotation.items():
            setattr(cls, field_name, field)

        super().__init_subclass__(**kwargs)

        # Set new default values if needed
        for attr_name, attr_type in cls.__annotations__.items():
            if not is_redis_field(attr_name, attr_type):
                continue
            if original_annotations[attr_name] == attr_type:
                serializer, validator = make_pickle_field_serializer(attr_name)
                setattr(cls, serializer.__name__, serializer)
                setattr(cls, validator.__name__, validator)
                continue

        # Update the redis model list for initialization
        # Skip dynamically created classes from type conversion
        if cls.__doc__ != DYNAMIC_CLASS_DOC and cls.Meta.init_with_rapyer:
            REDIS_MODELS.append(cls)

    @classmethod
    def create_expressions(cls, base_path: str = "") -> dict[str, Expression]:
        expressions = {}
        for field_name, field_info in cls.model_fields.items():
            full_field_name = rf"{base_path}\.{field_name}" if base_path else field_name
            field_type = field_info.annotation
            if safe_issubclass(field_type, AtomicRedisModel):
                expressions[field_name] = AtomicField(
                    field_name, **field_type.create_expressions(full_field_name)
                )
            else:
                expressions[field_name] = ExpressionField(full_field_name, field_type)
        return expressions

    @classmethod
    def init_class(cls):
        for field_name, field_expression in cls.create_expressions().items():
            setattr(cls, field_name, field_expression)

    def is_inner_model(self) -> bool:
        return bool(self.field_name)

    @deprecated(
        f"save function is deprecated and will become sync function in rapyer 1.2.0, use asave() instead"
    )
    async def save(self):
        return await self.asave()  # pragma: no cover

    async def asave(self) -> Self:
        model_dump = self.redis_dump()
        await self.Meta.redis.json().set(self.key, self.json_path, model_dump)
        if self.Meta.ttl is not None:
            nx = not self.Meta.refresh_ttl
            await self.Meta.redis.expire(self.key, self.Meta.ttl, nx=nx)
        return self

    def redis_dump(self):
        return self.model_dump(mode="json", context={REDIS_DUMP_FLAG_NAME: True})

    def redis_dump_json(self):
        return self.model_dump_json(context={REDIS_DUMP_FLAG_NAME: True})

    @deprecated(
        "duplicate function is deprecated and will be removed in rapyer 1.2.0, use aduplicate instead"
    )
    async def duplicate(self) -> Self:
        return await self.aduplicate()  # pragma: no cover

    async def aduplicate(self) -> Self:
        if self.is_inner_model():
            raise RuntimeError("Can only duplicate from top level model")

        duplicated = self.__class__(**self.model_dump())
        await duplicated.asave()
        return duplicated

    @deprecated(
        "duplicate_many function is deprecated and will be removed in rapyer 1.2.0, use aduplicate_many instead"
    )
    async def duplicate_many(self, num: int) -> list[Self]:
        return await self.aduplicate_many(num)  # pragma: no cover

    async def aduplicate_many(self, num: int) -> list[Self]:
        if self.is_inner_model():
            raise RuntimeError("Can only duplicate from top level model")

        duplicated_models = [self.__class__(**self.model_dump()) for _ in range(num)]
        await asyncio.gather(*[model.asave() for model in duplicated_models])
        return duplicated_models

    def update(self, **kwargs):
        for field_name, value in kwargs.items():
            setattr(self, field_name, value)

    async def aupdate(self, **kwargs):
        self.update(**kwargs)

        # Only serialize the updated fields using the include parameters
        serialized_fields = self.model_dump(
            mode="json",
            context={REDIS_DUMP_FLAG_NAME: True},
            include=set(kwargs.keys()),
        )
        json_path_kwargs = {
            f"{self.json_path}.{field_name}": serialized_fields[field_name]
            for field_name in kwargs.keys()
        }

        async with self.Meta.redis.pipeline() as pipe:
            update_keys_in_pipeline(pipe, self.key, **json_path_kwargs)
            await pipe.execute()
        await refresh_ttl_if_needed(
            self.Meta.redis, self.key, self.Meta.ttl, self.Meta.refresh_ttl
        )

    @classmethod
    @deprecated(
        "get() classmethod is deprecated and will be removed in rapyer 1.2.0, use aget instead"
    )
    async def get(cls, key: str) -> Self:
        return await cls.aget(key)  # pragma: no cover

    @classmethod
    async def aget(cls, key: str) -> Self:
        if cls._key_field_name and ":" not in key:
            key = f"{cls.class_key_initials()}:{key}"
        model_dump = await cls.Meta.redis.json().get(key, "$")
        if not model_dump:
            raise KeyNotFound(f"{key} is missing in redis")
        model_dump = model_dump[0]

        instance = cls.model_validate(model_dump, context={REDIS_DUMP_FLAG_NAME: True})
        instance.key = key
        await refresh_ttl_if_needed(
            cls.Meta.redis, key, cls.Meta.ttl, cls.Meta.refresh_ttl
        )
        return instance

    @deprecated(
        "load function is deprecated and will be removed in rapyer 1.2.0, use aload() instead"
    )
    async def load(self):
        return await self.aload()  # pragma: no cover

    async def aload(self) -> Self:
        model_dump = await self.Meta.redis.json().get(self.key, self.json_path)
        if not model_dump:
            raise KeyNotFound(f"{self.key} is missing in redis")
        model_dump = model_dump[0]
        instance = self.__class__(**model_dump)
        instance._pk = self._pk
        instance._base_model_link = self._base_model_link
        await refresh_ttl_if_needed(
            self.Meta.redis, self.key, self.Meta.ttl, self.Meta.refresh_ttl
        )
        return instance

    @classmethod
    async def afind(cls, *expressions):
        # Original behavior when no expressions provided - return all
        if not expressions:
            keys = await cls.afind_keys()
            if not keys:
                return []

            models = await cls.Meta.redis.json().mget(keys=keys, path="$")
        else:
            # With expressions - use Redis Search
            # Combine all expressions with & operator
            combined_expression = functools.reduce(lambda a, b: a & b, expressions)
            query_string = combined_expression.create_filter()

            # Create a Query object
            query = Query(query_string).no_content()

            # Try to search using the index
            index_name = cls.index_name()
            search_result = await cls.Meta.redis.ft(index_name).search(query)

            if not search_result.docs:
                return []

            # Get the keys from search results
            keys = [doc.id for doc in search_result.docs]

            # Fetch the actual documents
            models = await cls.Meta.redis.json().mget(keys=keys, path="$")

        if cls.Meta.ttl is not None and cls.Meta.refresh_ttl:
            async with cls.Meta.redis.pipeline() as pipe:
                for key in keys:
                    pipe.expire(key, cls.Meta.ttl)
                await pipe.execute()

        instances = []
        for model, key in zip(models, keys):
            model = cls.model_validate(model[0], context={REDIS_DUMP_FLAG_NAME: True})
            model.key = key
            instances.append(model)
        return instances

    @classmethod
    async def afind_keys(cls):
        return await cls.Meta.redis.keys(f"{cls.class_key_initials()}:*")

    @classmethod
    async def ainsert(cls, *models: Unpack[Self]):
        async with cls.Meta.redis.pipeline() as pipe:
            for model in models:
                pipe.json().set(model.key, model.json_path, model.redis_dump())
                if cls.Meta.ttl is not None:
                    pipe.expire(model.key, cls.Meta.ttl)
            await pipe.execute()

    @classmethod
    @deprecated(
        "function delete is deprecated and will be removed in rapyer 1.2.0, use adelete instead"
    )
    async def delete_by_key(cls, key: str) -> bool:
        return await cls.adelete_by_key(key)  # pragma: no cover

    @classmethod
    async def adelete_by_key(cls, key: str) -> bool:
        client = _context_var.get() or cls.Meta.redis
        return await client.delete(key) == 1

    @deprecated(
        "function delete is deprecated and will be removed in rapyer 1.2.0, use adelete instead"
    )
    async def delete(self):
        return await self.adelete()  # pragma: no cover

    async def adelete(self):
        if self.is_inner_model():
            raise RuntimeError("Can only delete from inner model")
        return await self.adelete_by_key(self.key)

    @classmethod
    async def adelete_many(cls, *args: Unpack[Self | str]):
        await cls.Meta.redis.delete(
            *[model if isinstance(model, str) else model.key for model in args]
        )

    @classmethod
    @contextlib.asynccontextmanager
    @deprecated(
        "lock_from_key function is deprecated and will be removed in rapyer 1.2.0, use alock_from_key instead"
    )
    async def lock_from_key(
        cls, key: str, action: str = "default", save_at_end: bool = False
    ) -> AbstractAsyncContextManager[Self]:
        async with cls.alock_from_key(  # pragma: no cover
            key, action, save_at_end  # pragma: no cover
        ) as redis_model:  # pragma: no cover
            yield redis_model  # pragma: no cover

    @classmethod
    @contextlib.asynccontextmanager
    async def alock_from_key(
        cls, key: str, action: str = "default", save_at_end: bool = False
    ) -> AbstractAsyncContextManager[Self]:
        async with acquire_lock(cls.Meta.redis, f"{key}/{action}"):
            redis_model = await cls.aget(key)
            yield redis_model
            if save_at_end:
                await redis_model.asave()

    @contextlib.asynccontextmanager
    @deprecated(
        "lock function is deprecated and will be removed in rapyer 1.2.0, use alock instead"
    )
    async def lock(
        self, action: str = "default", save_at_end: bool = False
    ) -> AbstractAsyncContextManager[Self]:
        async with self.alock_from_key(  # pragma: no cover
            self.key, action, save_at_end  # pragma: no cover
        ) as redis_model:  # pragma: no cover
            yield redis_model  # pragma: no cover

    @contextlib.asynccontextmanager
    async def alock(
        self, action: str = "default", save_at_end: bool = False
    ) -> AbstractAsyncContextManager[Self]:
        async with self.alock_from_key(self.key, action, save_at_end) as redis_model:
            unset_fields = {
                k: redis_model.__dict__[k] for k in redis_model.model_fields_set
            }
            self.__dict__.update(unset_fields)
            yield redis_model

    @contextlib.asynccontextmanager
    @deprecated(
        "pipeline function is deprecated and will be removed in rapyer 1.2.0, use apipeline instead"
    )
    async def pipeline(
        self, ignore_if_deleted: bool = False
    ) -> AbstractAsyncContextManager[Self]:
        async with self.apipeline(  # pragma: no cover
            ignore_if_deleted=ignore_if_deleted  # pragma: no cover
        ) as redis_model:  # pragma: no cover
            yield redis_model  # pragma: no cover

    @contextlib.asynccontextmanager
    async def apipeline(
        self, ignore_if_deleted: bool = False
    ) -> AbstractAsyncContextManager[Self]:
        async with self.Meta.redis.pipeline() as pipe:
            try:
                redis_model = await self.__class__.aget(self.key)
                unset_fields = {
                    k: redis_model.__dict__[k] for k in redis_model.model_fields_set
                }
                self.__dict__.update(unset_fields)
            except (TypeError, KeyNotFound):
                if ignore_if_deleted:
                    redis_model = self
                else:
                    raise
            _context_var.set(pipe)
            _context_xx_pipe.set(ignore_if_deleted)
            yield redis_model
            await pipe.execute()
            await refresh_ttl_if_needed(
                self.Meta.redis, self.key, self.Meta.ttl, self.Meta.refresh_ttl
            )
            _context_var.set(None)
            _context_xx_pipe.set(False)

    def __setattr__(self, name: str, value: Any) -> None:
        if name not in self.__annotations__ or value is None:
            super().__setattr__(name, value)
            return

        super().__setattr__(name, value)
        if value is not None:
            attr = getattr(self, name)
            if isinstance(attr, RedisType):
                attr._base_model_link = self

    def __eq__(self, other):
        if not isinstance(other, BaseModel):
            return False
        if self.__dict__ == other.__dict__:
            return True
        else:
            return super().__eq__(other)

    @model_validator(mode="before")
    @classmethod
    def validate_sub_model(cls, values):
        if isinstance(values, BaseModel) and not isinstance(values, cls):
            return values.model_dump()
        return values

    @model_validator(mode="after")
    def assign_fields_links(self):
        for field_name in self.__class__.model_fields.keys():
            attr = getattr(self, field_name)
            if isinstance(attr, RedisType) or isinstance(attr, AtomicRedisModel):
                attr._base_model_link = self
        return self


REDIS_MODELS: list[type[AtomicRedisModel]] = []


@deprecated(
    "get function is deprecated and will be removed in rapyer 1.2.0, use aget instead"
)
async def get(redis_key: str) -> AtomicRedisModel:
    return await aget(redis_key)  # pragma: no cover


async def aget(redis_key: str) -> AtomicRedisModel:
    redis_model_mapping = {klass.__name__: klass for klass in REDIS_MODELS}
    class_name = redis_key.split(":")[0]
    klass = redis_model_mapping.get(class_name)
    if klass is None:
        raise KeyNotFound(f"{redis_key} is missing in redis")
    return await klass.aget(redis_key)


def find_redis_models() -> list[type[AtomicRedisModel]]:
    return REDIS_MODELS


async def ainsert(*models: Unpack[AtomicRedisModel]) -> list[AtomicRedisModel]:
    async with AtomicRedisModel.Meta.redis.pipeline() as pipe:
        for model in models:
            pipe.json().set(model.key, model.json_path, model.redis_dump())
        await pipe.execute()
    return models


@contextlib.asynccontextmanager
async def alock_from_key(
    key: str, action: str = "default", save_at_end: bool = False
) -> AbstractAsyncContextManager[AtomicRedisModel | None]:
    async with acquire_lock(AtomicRedisModel.Meta.redis, f"{key}/{action}"):
        try:
            redis_model = await aget(key)
        except KeyNotFound:
            redis_model = None
        yield redis_model
        if save_at_end and redis_model is not None:
            await redis_model.asave()
