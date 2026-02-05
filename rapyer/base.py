import asyncio
import base64
import contextlib
import functools
import logging
import pickle
import uuid
from contextlib import AbstractAsyncContextManager
from typing import ClassVar, Any, get_origin, Optional

from pydantic import (
    BaseModel,
    PrivateAttr,
    ConfigDict,
    model_validator,
    field_serializer,
    field_validator,
    ValidationError,
)
from pydantic_core.core_schema import FieldSerializationInfo, ValidationInfo
from rapyer.config import RedisConfig
from rapyer.context import _context_var
from rapyer.errors.base import (
    KeyNotFound,
    PersistentNoScriptError,
    UnsupportedIndexedFieldError,
    CantSerializeRedisValueError,
    RapyerModelDoesntExistError,
)
from rapyer.fields.expression import ExpressionField, AtomicField, Expression
from rapyer.fields.index import IndexAnnotation
from rapyer.fields.key import KeyAnnotation
from rapyer.fields.safe_load import SafeLoadAnnotation
from rapyer.links import REDIS_SUPPORTED_LINK
from rapyer.scripts import registry as scripts_registry
from rapyer.types.base import RedisType, REDIS_DUMP_FLAG_NAME, FAILED_FIELDS_KEY
from rapyer.types.convert import RedisConverter
from rapyer.typing_support import Self, Unpack
from rapyer.utils.annotation import (
    replace_to_redis_types_in_annotation,
    has_annotation,
    field_with_flag,
    DYNAMIC_CLASS_DOC,
)
from rapyer.utils.fields import (
    get_all_pydantic_annotation,
    is_redis_field,
    is_type_json_serializable,
)
from rapyer.utils.pythonic import safe_issubclass
from rapyer.utils.redis import (
    acquire_lock,
    update_keys_in_pipeline,
)
from redis.commands.search.index_definition import IndexDefinition, IndexType
from redis.commands.search.query import Query
from redis.exceptions import NoScriptError, ResponseError

logger = logging.getLogger("rapyer")


def make_pickle_field_serializer(
    field: str, safe_load: bool = False, can_json: bool = False
):
    @field_serializer(field, when_used="json-unless-none")
    @classmethod
    def pickle_field_serializer(cls, v, info: FieldSerializationInfo):
        ctx = info.context or {}
        should_serialize_redis = ctx.get(REDIS_DUMP_FLAG_NAME, False)
        # Skip pickling if field CAN be JSON serialized AND user prefers JSON dump
        field_can_be_json = can_json and cls.Meta.prefer_normal_json_dump
        if should_serialize_redis and not field_can_be_json:
            return base64.b64encode(pickle.dumps(v)).decode("utf-8")
        return v

    pickle_field_serializer.__name__ = f"__serialize_{field}"

    @field_validator(field, mode="before")
    @classmethod
    def pickle_field_validator(cls, v, info: ValidationInfo):
        if v is None:
            return v
        ctx = info.context or {}
        should_serialize_redis = ctx.get(REDIS_DUMP_FLAG_NAME, False)
        if should_serialize_redis:
            try:
                field_can_be_json = can_json and cls.Meta.prefer_normal_json_dump
                if should_serialize_redis and not field_can_be_json:
                    return pickle.loads(base64.b64decode(v))
                return v
            except Exception as e:
                if safe_load:
                    failed_fields = ctx.setdefault(FAILED_FIELDS_KEY, set())
                    failed_fields.add(field)
                    logger.warning("SafeLoad: Failed to deserialize field '%s'", field)
                    return None
                raise CantSerializeRedisValueError() from e
        return v

    pickle_field_validator.__name__ = f"__deserialize_{field}"

    return pickle_field_serializer, pickle_field_validator


class AtomicRedisModel(BaseModel):
    _pk: str = PrivateAttr(default_factory=lambda: str(uuid.uuid4()))
    _base_model_link: Self | RedisType = PrivateAttr(default=None)
    _failed_fields: set[str] = PrivateAttr(default_factory=set)

    Meta: ClassVar[RedisConfig] = RedisConfig()
    _key_field_name: ClassVar[str | None] = None
    _safe_load_fields: ClassVar[set[str]] = set()
    _field_name: str = PrivateAttr(default="")
    model_config = ConfigDict(validate_assignment=True, validate_default=True)

    @property
    def failed_fields(self) -> set[str]:
        return self._failed_fields

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

    @property
    def client(self):
        return _context_var.get() or self.Meta.redis

    @classmethod
    def should_refresh(cls):
        return cls.Meta.refresh_ttl and cls.Meta.ttl is not None

    async def refresh_ttl_if_needed(self):
        if self.should_refresh():
            await self.Meta.redis.expire(self.key, self.Meta.ttl)

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
        # Find fields with KeyAnnotation and SafeLoadAnnotation
        cls._safe_load_fields = set()
        for field_name, annotation in cls.__annotations__.items():
            if has_annotation(annotation, KeyAnnotation):
                cls._key_field_name = field_name
            if has_annotation(annotation, SafeLoadAnnotation):
                cls._safe_load_fields.add(field_name)

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
                annotation,
                RedisConverter(
                    cls.Meta.redis_type,
                    f".{field_name}",
                    safe_load=field_name in cls._safe_load_fields
                    or cls.Meta.safe_load_all,
                ),
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
                default_value = cls.__dict__.get(attr_name, None)
                can_json = is_type_json_serializable(attr_type, default_value)
                should_json_serialize = can_json and cls.Meta.prefer_normal_json_dump

                if not should_json_serialize:
                    is_field_marked_safe = attr_name in cls._safe_load_fields
                    is_safe_load = is_field_marked_safe or cls.Meta.safe_load_all
                    serializer, validator = make_pickle_field_serializer(
                        attr_name, safe_load=is_safe_load, can_json=can_json
                    )
                    setattr(cls, serializer.__name__, serializer)
                    setattr(cls, validator.__name__, validator)

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

    async def asave(self) -> Self:
        model_dump = self.redis_dump()
        await self.client.json().set(self.key, self.json_path, model_dump)
        if self.Meta.ttl is not None:
            nx = not self.Meta.refresh_ttl
            await self.client.expire(self.key, self.Meta.ttl, nx=nx)
        return self

    def redis_dump(self):
        return self.model_dump(mode="json", context={REDIS_DUMP_FLAG_NAME: True})

    def redis_dump_json(self):
        return self.model_dump_json(context={REDIS_DUMP_FLAG_NAME: True})

    async def aduplicate(self) -> Self:
        if self.is_inner_model():
            raise RuntimeError("Can only duplicate from top level model")

        duplicated = self.__class__(**self.model_dump())
        await duplicated.asave()
        return duplicated

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

        async with self.Meta.redis.pipeline(transaction=True) as pipe:
            update_keys_in_pipeline(pipe, self.key, **json_path_kwargs)
            await pipe.execute()
        await self.refresh_ttl_if_needed()

    async def aset_ttl(self, ttl: int) -> None:
        if self.is_inner_model():
            raise RuntimeError("Can only set TTL from top level model")
        pipeline = _context_var.get()
        if pipeline is not None:
            pipeline.expire(self.key, ttl)
        else:
            await self.Meta.redis.expire(self.key, ttl)

    @classmethod
    async def aget(cls, key: str) -> Self:
        if cls._key_field_name and ":" not in key:
            key = f"{cls.class_key_initials()}:{key}"
        model_dump = await cls.Meta.redis.json().get(key, "$")
        if not model_dump:
            raise KeyNotFound(f"{key} is missing in redis")
        model_dump = model_dump[0]

        context = {REDIS_DUMP_FLAG_NAME: True, FAILED_FIELDS_KEY: set()}
        instance = cls.model_validate(model_dump, context=context)
        instance.key = key
        instance._failed_fields = context.get(FAILED_FIELDS_KEY, set())
        if cls.should_refresh():
            await cls.Meta.redis.expire(key, cls.Meta.ttl)
        return instance

    async def aload(self) -> Self:
        model_dump = await self.Meta.redis.json().get(self.key, self.json_path)
        if not model_dump:
            raise KeyNotFound(f"{self.key} is missing in redis")
        model_dump = model_dump[0]
        context = {REDIS_DUMP_FLAG_NAME: True, FAILED_FIELDS_KEY: set()}
        instance = self.__class__.model_validate(model_dump, context=context)
        instance._pk = self._pk
        instance._base_model_link = self._base_model_link
        instance._failed_fields = context.get(FAILED_FIELDS_KEY, set())
        await self.refresh_ttl_if_needed()
        return instance

    @classmethod
    def create_redis_model(cls, model_dump: dict, key: str) -> Optional[Self]:
        context = {REDIS_DUMP_FLAG_NAME: True, FAILED_FIELDS_KEY: set()}
        try:
            model = cls.model_validate(model_dump, context=context)
            model.key = key
        except ValidationError as exc:
            logger.debug(
                "Skipping key %s due to validation error during afind: %s",
                key,
                exc,
            )
            return None
        model.key = key
        model._failed_fields = context.get(FAILED_FIELDS_KEY, set())
        return model

    @classmethod
    async def afind(cls, *args):
        # Separate keys (str) from expressions (Expression)
        provided_keys = [arg for arg in args if isinstance(arg, str)]
        expressions = [arg for arg in args if isinstance(arg, Expression)]
        raise_on_missing = bool(provided_keys)

        if provided_keys and expressions:
            logger.warning(
                "afind called with both keys and expressions; expressions ignored"
            )

        if provided_keys:
            # Case 1: Extract by keys
            targeted_keys = [
                k if ":" in k else f"{cls.class_key_initials()}:{k}"
                for k in provided_keys
            ]
        elif expressions:
            # Case 2: Extract by expressions
            combined_expression = functools.reduce(lambda a, b: a & b, expressions)
            query_string = combined_expression.create_filter()
            query = Query(query_string).no_content()
            index_name = cls.index_name()
            search_result = await cls.Meta.redis.ft(index_name).search(query)
            if not search_result.docs:
                return []
            targeted_keys = [doc.id for doc in search_result.docs]
        else:
            # Case 3: Extract all
            targeted_keys = await cls.afind_keys()

        if not targeted_keys:
            return []

        # Fetch the actual documents
        models = await cls.Meta.redis.json().mget(keys=targeted_keys, path="$")

        instances = []
        for model, key in zip(models, targeted_keys):
            if model is None:
                if raise_on_missing:
                    raise KeyNotFound(f"{key} is missing in redis")
                continue
            if not cls.Meta.is_fake_redis:
                model = model[0]
            model = cls.create_redis_model(model, key)
            if model is None:
                continue
            instances.append(model)

        if cls.should_refresh():
            async with cls.Meta.redis.pipeline() as pipe:
                for model in instances:
                    pipe.expire(model.key, cls.Meta.ttl)
                await pipe.execute()

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
    async def adelete_by_key(cls, key: str) -> bool:
        client = _context_var.get() or cls.Meta.redis
        return await client.delete(key) == 1

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
    async def alock_from_key(
        cls, key: str, action: str = "default", save_at_end: bool = False
    ) -> AbstractAsyncContextManager[Self]:
        async with acquire_lock(cls.Meta.redis, f"{key}/{action}"):
            redis_model = await cls.aget(key)
            yield redis_model
            if save_at_end:
                await redis_model.asave()

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
    async def apipeline(
        self, ignore_redis_error: bool = False
    ) -> AbstractAsyncContextManager[Self]:
        async with apipeline(ignore_redis_error=ignore_redis_error):
            try:
                redis_model = await self.__class__.aget(self.key)
                unset_fields = {
                    k: redis_model.__dict__[k] for k in redis_model.model_fields_set
                }
                self.__dict__.update(unset_fields)
            except (TypeError, KeyNotFound):
                if ignore_redis_error:
                    redis_model = self
                else:
                    raise
            yield redis_model

            if self.should_refresh():
                pipe.expire(self.key, self.Meta.ttl)

    def __setattr__(self, name: str, value: Any) -> None:
        if name not in self.__annotations__ or value is None:
            super().__setattr__(name, value)
            return

        super().__setattr__(name, value)
        if value is not None:
            attr = getattr(self, name)
            if isinstance(attr, RedisType):
                attr._base_model_link = self

        pipeline = _context_var.get()
        if pipeline is not None:
            serialized = self.model_dump(
                mode="json",
                context={REDIS_DUMP_FLAG_NAME: True},
                include={name},
            )
            json_path = f"{self.json_path}.{name}"
            pipeline.json().set(self.key, json_path, serialized[name])

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


async def aget(redis_key: str) -> AtomicRedisModel:
    redis_model_mapping = {klass.__name__: klass for klass in REDIS_MODELS}
    class_name = redis_key.split(":")[0]
    klass = redis_model_mapping.get(class_name)
    if klass is None:
        raise KeyNotFound(f"{redis_key} is missing in redis")
    return await klass.aget(redis_key)


async def afind(*redis_keys: str, skip_missing: bool = False) -> list[AtomicRedisModel]:
    if not redis_keys:
        return []

    redis_model_mapping = {klass.__name__: klass for klass in REDIS_MODELS}

    key_to_class: dict[str, type[AtomicRedisModel]] = {}
    for key in redis_keys:
        class_name = key.split(":")[0]
        if class_name not in redis_model_mapping:
            raise RapyerModelDoesntExistError(
                class_name, f"Unknown model class: {class_name}"
            )
        key_to_class[key] = redis_model_mapping[class_name]

    models_data = await AtomicRedisModel.Meta.redis.json().mget(
        keys=redis_keys, path="$"
    )

    instances = []
    instances_by_class: dict[type[AtomicRedisModel], list[AtomicRedisModel]] = {}

    for data, key in zip(models_data, redis_keys):
        if data is None:
            if not skip_missing:
                raise KeyNotFound(f"{key} is missing in redis")
            continue
        klass = key_to_class[key]
        if not klass.Meta.is_fake_redis:
            data = data[0]
        model = klass.create_redis_model(data, key)
        if model is None:
            continue
        instances.append(model)
        instances_by_class.setdefault(klass, []).append(model)

    async with AtomicRedisModel.Meta.redis.pipeline() as pipe:
        for klass, class_instances in instances_by_class.items():
            if klass.should_refresh():
                for model in class_instances:
                    pipe.expire(model.key, klass.Meta.ttl)
        await pipe.execute()

    return instances


def find_redis_models() -> list[type[AtomicRedisModel]]:
    return REDIS_MODELS


async def ainsert(*models: Unpack[AtomicRedisModel]) -> list[AtomicRedisModel]:
    async with AtomicRedisModel.Meta.redis.pipeline() as pipe:
        for model in models:
            pipe.json().set(model.key, model.json_path, model.redis_dump())
            if model.Meta.ttl is not None:
                pipe.expire(model.key, model.Meta.ttl)
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


@contextlib.asynccontextmanager
async def apipeline(ignore_redis_error: bool = False) -> AbstractAsyncContextManager:
    async with AtomicRedisModel.Meta.redis.pipeline(transaction=True) as pipe:
        pipe_prev = _context_var.set(pipe)
        yield
        commands_backup = list(pipe.command_stack)
        noscript_on_first_attempt = False
        noscript_on_retry = False

        try:
            await pipe.execute()
        except NoScriptError:
            noscript_on_first_attempt = True
        except ResponseError as exc:
            if ignore_redis_error:
                logger.warning(
                    "Swallowed ResponseError during pipeline.execute() with "
                    "ignore_redis_error=True for key %r: %s",
                    getattr(self, "key", None),
                    exc,
                )
            else:
                raise

        if noscript_on_first_attempt:
            await scripts_registry.handle_noscript_error(self.Meta.redis, self.Meta)
            evalsha_commands = [
                (args, options)
                for args, options in commands_backup
                if args[0] == "EVALSHA"
            ]
            # Retry execute the pipeline actions
            async with self.Meta.redis.pipeline(transaction=True) as retry_pipe:
                for args, options in evalsha_commands:
                    retry_pipe.execute_command(*args, **options)
                try:
                    await retry_pipe.execute()
                except NoScriptError:
                    noscript_on_retry = True

        if noscript_on_retry:
            raise PersistentNoScriptError(
                "NOSCRIPT error persisted after re-registering scripts. "
                "This indicates a server-side problem with Redis."
            )

        _context_var.set(pipe_prev)
