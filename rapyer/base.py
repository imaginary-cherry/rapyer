import base64
import contextlib
import functools
import logging
import pickle
import uuid
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager
from typing import Any, ClassVar, Optional, get_origin

from pydantic import (
    BaseModel,
    ConfigDict,
    PrivateAttr,
    ValidationError,
    field_serializer,
    field_validator,
    model_validator,
)
from pydantic_core.core_schema import FieldSerializationInfo, ValidationInfo
from redis.asyncio.client import Pipeline
from redis.commands.search.aggregation import AggregateRequest
from redis.commands.search.index_definition import IndexDefinition, IndexType
from redis.commands.search.query import Query
from redis.exceptions import NoScriptError, ResponseError

from rapyer.actions import (
    ActionGroup,
    TargetSource,
    mark_actions,
    register_action_target,
    should_refresh_for_action,
)
from rapyer.config import RedisConfig
from rapyer.context import (
    _context_pipe,
    ensure_pipeline,
    pipe_ctx_from_redix,
    pipeline_with_execution,
    with_pipe_context,
)
from rapyer.errors import (
    CantSerializeRedisValueError,
    KeyNotFound,
    MissingParameterError,
    PersistentNoScriptError,
    RapyerModelDoesntExistError,
    UnsupportedArgumentTypeError,
    UnsupportedArgumentValueError,
    UnsupportedIndexedFieldError,
    UpdateAtomicModelError,
)
from rapyer.fields.expression import AtomicField, Expression, ExpressionField
from rapyer.fields.index import IndexAnnotation
from rapyer.fields.key import KeyAnnotation, RapyerKey
from rapyer.fields.safe_load import SafeLoadAnnotation
from rapyer.links import ATOMIC_MODEL_API_REF_LINK, REDIS_SUPPORTED_LINK
from rapyer.result import DeleteResult, RapyerDeleteResult
from rapyer.scripts import registry as scripts_registry
from rapyer.types.base import (
    FAILED_FIELDS_KEY,
    REDIS_DUMP_FLAG_NAME,
    BaseRedisType,
    RedisType,
)
from rapyer.types.convert import RedisConverter
from rapyer.types.special import SpecialFieldType
from rapyer.typing_support import Self, Unpack
from rapyer.utils.annotation import (
    DYNAMIC_CLASS_DOC,
    field_with_flag,
    has_annotation,
    replace_to_redis_types_in_annotation,
)
from rapyer.utils.fields import (
    get_all_pydantic_annotation,
    is_redis_field,
    is_type_json_serializable,
)
from rapyer.utils.pythonic import safe_issubclass
from rapyer.utils.redis import (
    acquire_lock,
    batched,
    delete_in_batches,
    scan_keys,
    update_keys_in_pipeline,
)

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
    _base_model_link: Self | BaseRedisType = PrivateAttr(default=None)
    _failed_fields: set[str] = PrivateAttr(default_factory=set)

    Meta: ClassVar[RedisConfig] = RedisConfig()
    _key_field_name: ClassVar[str | None] = None
    _safe_load_fields: ClassVar[set[str]] = set()
    _special_field_names: ClassVar[set[str]] = set()
    _field_name: str = PrivateAttr(default="")
    model_config = ConfigDict(validate_assignment=True, validate_default=True)

    @property
    def failed_fields(self) -> set[str]:
        return self._failed_fields

    @property
    def pk(self):
        if self._key_field_name:
            return self.model_dump(include={self._key_field_name})[self._key_field_name]
        return RapyerKey(self._pk)

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
        return _context_pipe.get() or self.Meta.redis

    @classmethod
    def should_refresh_for_action(cls, action=None):
        if action is None:
            action = ActionGroup.all()
        return should_refresh_for_action(cls.Meta, action)

    @classmethod
    def should_refresh(cls):
        return cls.should_refresh_for_action()

    async def refresh_ttl_if_needed(
        self,
        can_use_pipeline: bool = False,
        action=None,
        initial: bool = False,
    ):
        if self.Meta.ttl is None:
            return
        should_refresh = self.should_refresh_for_action(action)
        if not should_refresh and not initial:
            return
        # initial=True with refresh_ttl=False → set TTL only if none exists (NX)
        nx = initial and not should_refresh
        pipe_context = (
            ensure_pipeline if can_use_pipeline else pipeline_with_execution
        )
        async with pipe_context(self.Meta) as pipe:
            pipe.expire(self.key, self.Meta.ttl, nx=nx)
            for fname in self._special_field_names:
                field = getattr(self, fname)
                if isinstance(field, SpecialFieldType):
                    pipe.expire(field.special_key, self.Meta.ttl, nx=nx)

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
    def key(self) -> RapyerKey:
        if self._base_model_link:
            return self._base_model_link.key
        return RapyerKey(f"{self.key_initials}:{self.pk}")

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

        # Detect special field types
        cls._special_field_names = set(getattr(cls, "_special_field_names", set()))
        for field_name, annotation in cls.__annotations__.items():
            origin = get_origin(annotation) or annotation
            if safe_issubclass(origin, SpecialFieldType):
                cls._special_field_names.add(field_name)

        super().__init_subclass__(**kwargs)

        # Set new default values if needed
        for attr_name, attr_type in cls.__annotations__.items():
            if not is_redis_field(attr_name, attr_type):
                continue
            if safe_issubclass(attr_type, RapyerKey):
                continue
            # Skip special fields — they handle their own serialization
            if attr_name in cls._special_field_names:
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

    @mark_actions(ActionGroup.UPDATE, initial=True)
    async def asave(self) -> Self:
        model_dump = self.redis_dump()
        async with ensure_pipeline(self.Meta) as pipe:
            pipe.json().set(self.key, self.json_path, model_dump)
            for fname in self._special_field_names:
                field = getattr(self, fname)
                if isinstance(field, SpecialFieldType):
                    await field.asave_special()
        return self

    def redis_dump(self):
        return self.model_dump(
            mode="json",
            context={REDIS_DUMP_FLAG_NAME: True},
            exclude=self._special_field_names or None,
        )

    def redis_dump_json(self):
        return self.model_dump_json(
            context={REDIS_DUMP_FLAG_NAME: True},
            exclude=self._special_field_names or None,
        )

    @mark_actions(ActionGroup.UPDATE, target=TargetSource.RESULT, initial=True)
    async def aduplicate(self) -> Self:
        if self.is_inner_model():
            raise RuntimeError("Can only duplicate from top level model")

        duplicated = self.__class__(**self.model_dump())
        async with ensure_pipeline(self.Meta):
            await duplicated.asave()
            for fname in self._special_field_names:
                source_field = getattr(self, fname)
                target_field = getattr(duplicated, fname)
                if isinstance(source_field, SpecialFieldType):
                    await source_field.aduplicate_special(target_field.special_key)
        return duplicated

    @mark_actions(ActionGroup.UPDATE, target=TargetSource.RESULT, initial=True)
    async def aduplicate_many(self, num: int) -> list[Self]:
        if self.is_inner_model():
            raise RuntimeError("Can only duplicate from top level model")

        duplicated_models = [self.__class__(**self.model_dump()) for _ in range(num)]
        async with ensure_pipeline(self.Meta):
            await self.ainsert(*duplicated_models)
            for fname in self._special_field_names:
                source_field = getattr(self, fname)
                if isinstance(source_field, SpecialFieldType):
                    for dup in duplicated_models:
                        target_field = getattr(dup, fname)
                        await source_field.aduplicate_special(target_field.special_key)
        return duplicated_models

    def update(self, **kwargs):
        for field_name, value in kwargs.items():
            setattr(self, field_name, value)

    @mark_actions(ActionGroup.UPDATE)
    async def aupdate(self, **kwargs):
        # Special fields (e.g. RedisPriorityQueue) manage their own separate
        # Redis storage and cannot be serialized as JSON path updates.
        special_in_kwargs = self._special_field_names & set(kwargs.keys())
        if special_in_kwargs:
            raise UpdateAtomicModelError(
                f"Cannot update special fields via aupdate: {special_in_kwargs}. "
                f"Special fields manage their own Redis storage and cannot be "
                f"serialized as JSON path updates."
            )
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

        async with ensure_pipeline(self.Meta) as pipe:
            update_keys_in_pipeline(pipe, self.key, **json_path_kwargs)

    async def aset_ttl(self, ttl: int) -> None:
        if self.is_inner_model():
            raise RuntimeError("Can only set TTL from top level model")
        async with ensure_pipeline(self.Meta) as pipe:
            pipe.expire(self.key, ttl)
            for fname in self._special_field_names:
                field = getattr(self, fname)
                if isinstance(field, SpecialFieldType):
                    pipe.expire(field.special_key, ttl)

    @functools.cached_property
    def all_keys(self) -> list[str]:
        return self._all_keys_for_key(self.key)

    @classmethod
    def _all_keys_for_key(cls, key: str) -> list[str]:
        keys = [key]
        for fname in cls._special_field_names:
            keys.append(f"{key}:{fname}")
        return keys

    @classmethod
    def _resolve_key(cls, key: str | Self) -> str:
        if isinstance(key, AtomicRedisModel):
            return key.key
        if ":" not in key:
            return f"{cls.class_key_initials()}:{key}"
        return key

    @classmethod
    async def aget(cls, key: str) -> Self:
        key = cls._resolve_key(key)
        model_dump = await cls.Meta.redis.json().get(key, "$")  # type: ignore[misc]
        if not model_dump:
            raise KeyNotFound(f"{key} is missing in redis")
        model_dump = model_dump[0]

        context = {REDIS_DUMP_FLAG_NAME: True, FAILED_FIELDS_KEY: set()}
        instance = cls.model_validate(model_dump, context=context)
        instance.key = key
        instance._failed_fields = context.get(FAILED_FIELDS_KEY, set())
        if cls.should_refresh_for_action(ActionGroup.READ):
            await instance.refresh_ttl_if_needed(action=ActionGroup.READ)
        return instance

    @mark_actions(ActionGroup.READ)
    async def aload(self) -> Self:
        model_dump = await self.Meta.redis.json().get(self.key, self.json_path)  # type: ignore[misc]
        if not model_dump:
            raise KeyNotFound(f"{self.key} is missing in redis")
        model_dump = model_dump[0]
        context = {REDIS_DUMP_FLAG_NAME: True, FAILED_FIELDS_KEY: set()}
        instance = self.__class__.model_validate(model_dump, context=context)
        instance._pk = self._pk
        instance._base_model_link = self._base_model_link
        instance._failed_fields = context.get(FAILED_FIELDS_KEY, set())
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
    async def afind(cls, *args, max_results: Optional[int] = None) -> list[Self]:
        if max_results is not None and max_results < 0:
            raise UnsupportedArgumentValueError(
                f"max_results must be >= 0, got {max_results}"
            )
        # Separate keys (str) from expressions (Expression)
        provided_keys = [arg for arg in args if isinstance(arg, str)]
        expressions = [arg for arg in args if isinstance(arg, Expression)]
        raise_on_missing = bool(provided_keys)

        # TODO - in 1.3.0 this should raise an error
        if provided_keys and expressions:
            logger.warning(
                "afind called with both keys and expressions; expressions ignored"
            )

        if provided_keys:
            # Case 1: Extract by keys
            targeted_keys = [cls._resolve_key(k) for k in provided_keys]
            if max_results is not None:
                targeted_keys = targeted_keys[:max_results]
        elif expressions:
            # Case 2: Extract by expressions
            combined_expression = functools.reduce(lambda a, b: a & b, expressions)
            query_string = combined_expression.create_filter()
            targeted_keys = await cls._search_keys_by_query(query_string, max_results)
            if not targeted_keys:
                return []
        else:
            # Case 3: Extract all
            targeted_keys = await cls.afind_keys(max_results)

        if not targeted_keys:
            return []

        # Fetch the actual documents
        models = await cls.Meta.redis.json().mget(keys=targeted_keys, path="$")  # type: ignore[misc]

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

        if cls.should_refresh_for_action(ActionGroup.READ):
            async with pipe_ctx_from_redix(cls.Meta.redis) as pipe:
                for model in instances:
                    await model.refresh_ttl_if_needed(can_use_pipeline=True, action=ActionGroup.READ)
                await pipe.execute()

        return instances

    @classmethod
    async def afind_one(cls, *args) -> Optional[Self]:
        results = await cls.afind(*args, max_results=1)
        return results[0] if results else None

    @classmethod
    async def afind_keys(cls, max_results: Optional[int] = None) -> list[RapyerKey]:
        pattern = f"{cls.class_key_initials()}:*"
        if max_results is None:
            keys = await cls.Meta.redis.keys(pattern)
        else:
            keys = await scan_keys(cls.Meta.redis, pattern, max_results)
        return [RapyerKey(k) for k in keys]

    @classmethod
    @mark_actions(ActionGroup.UPDATE, target=TargetSource.MANUAL, initial=True)
    async def ainsert(cls, *models: Unpack[Self]):
        async with ensure_pipeline(cls.Meta) as pipe:
            for model in models:
                register_action_target(model, ActionGroup.UPDATE, initial=True)
                pipe.json().set(model.key, model.json_path, model.redis_dump())
                for fname in cls._special_field_names:
                    field = getattr(model, fname)
                    if isinstance(field, SpecialFieldType):
                        await field.asave_special()

    @classmethod
    async def adelete_by_key(cls, key: str) -> bool:
        key = cls._resolve_key(key)
        keys_to_delete = cls._all_keys_for_key(key)
        in_outer_pipe = _context_pipe.get() is not None
        async with ensure_pipeline(cls.Meta, should_execute=False) as pipe:
            pipe.delete(*keys_to_delete)
            if in_outer_pipe:
                # Outer caller owns execution; we cannot observe the result here.
                return True
            results = await pipe.execute()
        return sum(results) > 0

    async def adelete(self):
        if self.is_inner_model():
            raise RuntimeError("Can only delete from inner model")
        return await self.adelete_by_key(self.key)

    @classmethod
    async def aexists(cls, key: str | Self) -> bool:
        key = cls._resolve_key(key)
        client = _context_pipe.get() or cls.Meta.redis
        return await client.exists(key) == 1

    @classmethod
    async def _search_keys_by_query(
        cls, query_string: str, max_results: Optional[int] = None
    ) -> list[str]:
        query = Query(query_string).no_content()
        if max_results is not None:
            query = query.paging(0, max_results)
        index_name = cls.index_name()
        search_result = await cls.Meta.redis.ft(index_name).search(query)
        return [doc.id for doc in search_result.docs]

    @classmethod
    async def iter_filter_batches(
        cls, query_string: str, batch_size: int
    ) -> AsyncIterator[list[str]]:
        agg_request = (
            AggregateRequest(query_string).load("@__key").cursor(count=batch_size)
        )
        index_name = cls.index_name()
        result = await cls.Meta.redis.ft(index_name).aggregate(agg_request)
        if result.rows:
            yield [row[1] for row in result.rows]
        while result.cursor and result.cursor.cid != 0:
            result = await cls.Meta.redis.ft(index_name).aggregate(result.cursor)
            if result.rows:
                yield [row[1] for row in result.rows]

    @classmethod
    async def _iter_expanded_filter_batches(
        cls,
        query_string: str,
        batch_size: int,
        collected_keys: list[str],
    ) -> AsyncIterator[list[str]]:
        async for batch in cls.iter_filter_batches(query_string, batch_size):
            collected_keys.extend(batch)
            yield [k for key in batch for k in cls._all_keys_for_key(key)]

    @classmethod
    async def adelete_many(
        cls, *args: Self | RapyerKey | str | Expression
    ) -> DeleteResult:
        if not args:
            raise UnsupportedArgumentTypeError(
                f"adelete_many requires at least one argument, see {ATOMIC_MODEL_API_REF_LINK}"
            )

        provided_keys, model_instances, expressions = categorize_delete_args(
            args, allow_expressions=True
        )

        if expressions and (provided_keys or model_instances):
            raise UnsupportedArgumentTypeError(
                "Cannot mix expressions with keys or model instances in adelete_many"
            )

        max_batch = cls.Meta.max_delete_per_transaction
        should_batch = _context_pipe.get() is None and max_batch is not None
        batches = None
        targeted_keys = None

        if provided_keys or model_instances:
            # Get all keys for the models, including detached speical field keys
            all_keys = [k for m in model_instances for k in m.all_keys]
            for key in provided_keys:
                all_keys.extend(cls._all_keys_for_key(cls._resolve_key(key)))
            targeted_keys = [
                cls._resolve_key(k) for k in provided_keys + model_instances
            ]
            if all_keys:
                batch_size = max_batch if should_batch else len(all_keys)
                batches = batched(all_keys, batch_size)
        elif expressions:
            combined_expression = functools.reduce(lambda a, b: a & b, expressions)
            query_string = combined_expression.create_filter()
            if should_batch:
                targeted_keys = []
                batches = cls._iter_expanded_filter_batches(
                    query_string, max_batch, targeted_keys
                )
            else:
                targeted_keys = await cls._search_keys_by_query(query_string)
                if targeted_keys:
                    all_keys = [
                        k for key in targeted_keys for k in cls._all_keys_for_key(key)
                    ]
                    batches = batched(all_keys, len(all_keys))

        if batches is None:
            return DeleteResult(models_deleted=0, keys_deleted=0)

        keys_deleted, was_commited = await delete_in_batches(cls.Meta.redis, batches)
        models_deleted = len(targeted_keys) if targeted_keys else 0
        return DeleteResult(
            models_deleted=models_deleted,
            keys_deleted=keys_deleted,
            was_committed=was_commited,
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
        self, ignore_redis_error: bool = False, use_existing_pipe: bool = False
    ) -> AbstractAsyncContextManager[Self]:
        async with apipeline(
            ignore_redis_error=ignore_redis_error,
            use_existing_pipe=use_existing_pipe,
            _meta=self.Meta,
        ) as pipe:
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
        skip_redis_set = False
        if isinstance(value, BaseRedisType):
            skip_redis_set = value._redis_updated
            value._redis_updated = False

        super().__setattr__(name, value)
        if name not in self.__class__.model_fields or value is None:
            return

        if value is not None:
            attr = getattr(self, name)
            if isinstance(attr, BaseRedisType):
                attr._base_model_link = self

        if skip_redis_set:
            return

        # Special fields manage their own Redis storage
        if name in self.__class__._special_field_names:
            return

        pipeline = _context_pipe.get()
        # We need to update the redis only for non redis type - redis types update themselves
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
            if isinstance(attr, (BaseRedisType, AtomicRedisModel)):
                attr._base_model_link = self
        return self


REDIS_MODELS: list[type[AtomicRedisModel]] = []


def categorize_delete_args(
    args: tuple, allow_expressions: bool = False
) -> tuple[list[RapyerKey], list[AtomicRedisModel], list[Expression]]:
    keys, model_instances, expressions = [], [], []
    for arg in args:
        if isinstance(arg, RapyerKey):
            keys.append(arg)
        elif isinstance(arg, str):
            keys.append(RapyerKey(arg))
        elif isinstance(arg, AtomicRedisModel):
            model_instances.append(arg)
        elif allow_expressions and isinstance(arg, Expression):
            expressions.append(arg)
        else:
            raise UnsupportedArgumentTypeError(
                f"{arg} is not a valid for adelete_many, see {ATOMIC_MODEL_API_REF_LINK}"
            )
    return keys, model_instances, expressions


def _resolve_model_class(redis_key: str) -> type[AtomicRedisModel] | None:
    redis_model_mapping = {klass.__name__: klass for klass in REDIS_MODELS}
    class_name = redis_key.split(":")[0]
    return redis_model_mapping.get(class_name)


async def aget(redis_key: str) -> AtomicRedisModel:
    klass = _resolve_model_class(redis_key)
    if klass is None:
        raise KeyNotFound(f"{redis_key} is missing in redis")
    return await klass.aget(redis_key)


async def afind_one(redis_key: str) -> Optional[AtomicRedisModel]:
    try:
        return await aget(redis_key)
    except KeyNotFound:
        return None


async def aexists(redis_key: str | AtomicRedisModel) -> bool:
    if isinstance(redis_key, AtomicRedisModel):
        redis_key = redis_key.key
    klass = _resolve_model_class(redis_key)
    if klass is None:
        return False
    return await klass.aexists(redis_key)


@mark_actions(ActionGroup.READ, target=TargetSource.RESULT)
async def afind(*redis_keys: str, skip_missing: bool = False) -> list[AtomicRedisModel]:
    if not redis_keys:
        return []

    key_to_class: dict[str, type[AtomicRedisModel]] = {}
    for key in redis_keys:
        klass = _resolve_model_class(key)
        if klass is None:
            class_name = key.split(":")[0]
            raise RapyerModelDoesntExistError(
                class_name, f"Unknown model class: {class_name}"
            )
        key_to_class[key] = klass

    models_data = await AtomicRedisModel.Meta.redis.json().mget(  # type: ignore[misc]
        keys=redis_keys, path="$"
    )

    instances = []

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

    return instances


def find_redis_models() -> list[type[AtomicRedisModel]]:
    return REDIS_MODELS


@mark_actions(ActionGroup.UPDATE, target=TargetSource.MANUAL, initial=True)
async def ainsert(*models: Unpack[AtomicRedisModel]) -> list[AtomicRedisModel]:
    async with AtomicRedisModel.Meta.redis.pipeline() as pipe:
        with with_pipe_context(pipe):
            for model in models:
                register_action_target(model, ActionGroup.UPDATE, initial=True)
                pipe.json().set(model.key, model.json_path, model.redis_dump())
                for fname in model.__class__._special_field_names:
                    field = getattr(model, fname)
                    if isinstance(field, SpecialFieldType):
                        await field.asave_special()
            await pipe.execute()
    return models


async def adelete_many(*args: RapyerKey | str | AtomicRedisModel) -> RapyerDeleteResult:
    if not args:
        raise MissingParameterError("adelete_many requires at least one argument")

    string_keys, model_instances, _ = categorize_delete_args(args)

    key_to_class: dict[str, type[AtomicRedisModel]] = {}
    validated_keys = []

    for key in string_keys:
        klass = _resolve_model_class(key)
        if klass is None:
            class_name = key.split(":")[0]
            raise RapyerModelDoesntExistError(
                class_name, f"Unknown model class: {class_name}"
            )
        key_to_class[key] = klass
        validated_keys.append(key)

    for instance in model_instances:
        key = instance.key
        key_to_class[key] = instance.__class__
        validated_keys.append(key)

    redis = AtomicRedisModel.Meta.redis
    max_batch = AtomicRedisModel.Meta.max_delete_per_transaction
    should_batch = _context_pipe.get() is None and max_batch is not None

    all_keys = []
    for key in validated_keys:
        klass = key_to_class[key]
        all_keys.extend(klass._all_keys_for_key(key))

    batch_size = max_batch if should_batch else len(all_keys)
    batches = batched(all_keys, batch_size)
    keys_deleted, was_commited = await delete_in_batches(redis, batches)
    models_deleted = len(validated_keys)

    per_class_count: dict[type[AtomicRedisModel], int] = {}
    for key in validated_keys:
        klass = key_to_class[key]
        per_class_count[klass] = per_class_count.get(klass, 0) + 1

    return RapyerDeleteResult(
        models_deleted=models_deleted,
        keys_deleted=keys_deleted,
        by_model=per_class_count,
        was_committed=was_commited,
    )


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
async def apipeline(
    ignore_redis_error: bool = False,
    use_existing_pipe: bool = False,
    _meta: RedisConfig = None,
) -> AbstractAsyncContextManager[Pipeline]:
    pipe = _context_pipe.get()
    if use_existing_pipe and pipe is not None:
        yield pipe
    else:
        async with _apipeline(ignore_redis_error, _meta) as pipe:
            yield pipe


@contextlib.asynccontextmanager
async def _apipeline(
    ignore_redis_error: bool = False, _meta: RedisConfig = None
) -> AbstractAsyncContextManager[Pipeline]:
    _meta = _meta or AtomicRedisModel.Meta
    redis = _meta.redis
    async with redis.pipeline(transaction=True) as pipe:
        with with_pipe_context(pipe):
            yield pipe
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
                        "ignore_redis_error=True: %s",
                        exc,
                    )
                else:
                    raise

            if noscript_on_first_attempt:
                await scripts_registry.handle_noscript_error(redis, _meta)
                evalsha_commands = [
                    (args, options)
                    for args, options in commands_backup
                    if args[0] == "EVALSHA"
                ]
                # Retry execute the pipeline actions
                async with redis.pipeline(transaction=True) as retry_pipe:
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
