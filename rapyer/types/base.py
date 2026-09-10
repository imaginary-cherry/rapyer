import abc
import base64
import pickle
from abc import ABC
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    ClassVar,
    Optional,
    get_args,
    get_origin,
)

from pydantic import GetCoreSchemaHandler, TypeAdapter
from pydantic_core import core_schema
from redis.commands.search.field import TextField

# Imported here to avoid circular import issues; actions imports context, not types.base
from rapyer.actions import ActionGroup, install_marked_action_methods, mark_actions
from rapyer.capabilities import ParentLinked
from rapyer.context import _context_pipe, get_pipe_json
from rapyer.types.traits import FieldTrait
from rapyer.typing_support import Self
from rapyer.utils.annotation import annotation_origin
from rapyer.utils.pythonic import resolve_generic_args, safe_issubclass

if TYPE_CHECKING:
    from rapyer.config import RedisConfig

REDIS_DUMP_FLAG_NAME = "__rapyer_dumped__"
FAILED_FIELDS_KEY = "__rapyer_failed_fields__"


class BaseRedisType(ParentLinked, ABC):
    """Common base for all Redis-aware field types (inline and special)."""

    _adapter: TypeAdapter = None
    field_name: str

    # The plain Python type this redis type wraps (e.g. ``int``, ``str``, ``list``).
    wrapped_python_type: ClassVar[type]

    def __init_subclass__(cls, *, owner_meta: Optional["RedisConfig"] = None, **kwargs):
        super().__init_subclass__(**kwargs)
        if owner_meta is None:
            # Static module-load-time subclass: no Atomic to specialize for, so methods stay
            # tagged with v2 MarkActionParams for RedisConverter's per-field subclass to install.
            return
        cls.build_redis_model(owner_meta)

    @classmethod
    def build_redis_model(cls, meta: "RedisConfig"):
        """
        Re-install marked-action methods on this per-field subclass.

        Mirror of ``AtomicRedisModel.build_redis_model`` for the field-type
        side: dynamic per-field subclasses (created by ``RedisConverter``)
        decide wrap/no-wrap of each method against the owning model's meta at
        build time. Tests/benchmarks that mutate ``Meta`` at runtime can call
        this directly via the test-side ``recursive_build_redis_model`` helper.
        """
        install_marked_action_methods(cls, meta)

    @classmethod
    def element_annotations(cls, annotation) -> tuple:
        """This type's generic arguments, each keeping its own ``Annotated`` metadata."""
        inner = annotation
        while get_origin(inner) is Annotated:
            inner = get_args(inner)[0]
        # A bare class falls back to __orig_bases__, which is where a per-field
        # subclass keeps the arguments its annotation was built from.
        return resolve_generic_args(inner)

    @classmethod
    def resolve_configs(cls, annotation) -> tuple:
        """Every config declared at or under this annotation, in declaration order."""
        found: list = []
        for arg in cls.element_annotations(annotation):
            element = annotation_origin(arg)
            if safe_issubclass(element, BaseRedisType):
                found.extend(element.resolve_configs(arg))
        return tuple(found)

    @classmethod
    def container_kind(cls) -> Optional[str]:
        """The Redis structure this type keeps its elements in, outside the parent JSON."""
        return None

    @classmethod
    def traits(cls) -> FieldTrait:
        """What this type itself contributes to a walk."""
        return FieldTrait(0)

    @classmethod
    def reachable_fields_w_traits(cls) -> FieldTrait:
        """What is reachable strictly inside this type, never including its own."""
        return FieldTrait(0)

    @classmethod
    def queue_special_loads_in_pipeline(
        cls, pipe, key: str, plan: list, parent_path: str = "", field_name: str = ""
    ):
        """Queue any special-field loads this type contributes into ``pipe``., it will be used by the pipe creator"""
        return

    @property
    def redis(self):
        return self._base_model_link.Meta.redis

    @property
    def key(self):
        return self._base_model_link.key

    @property
    def Meta(self):
        return self._base_model_link.Meta

    @property
    def field_path(self) -> str:
        base_path = self._base_model_link.field_path
        return f"{base_path}{self.field_name}"

    @property
    def pipeline(self):
        return _context_pipe.get()

    @property
    def pipeline_json(self):
        return get_pipe_json()

    @property
    def client(self):
        return _context_pipe.get() or self.redis

    @property
    def client_json(self):
        return get_pipe_json() or self.Meta.redis_json

    @property
    def json_path(self):
        return f"${self.field_path}"

    def __init__(self, *args, **kwargs):
        self._base_model_link = None
        self._redis_updated = False
        self.field_name = ""

    def link_to_parent(self, parent: ParentLinked, path_segment: str):
        self._base_model_link = parent
        self.field_name = path_segment

    def init_redis_field(self, key, val):
        if isinstance(val, ParentLinked):
            val.link_to_parent(self, key)

    def sub_field_path(self, key: str):
        return f"{self.field_path}.{key}"

    def json_field_path(self, field_name: str):
        return f"${self.sub_field_path(field_name)}"


class RedisType(BaseRedisType):

    @mark_actions(ActionGroup.UPDATE)
    async def asave(self) -> Self:
        model_dump = self._adapter.dump_python(
            self, mode="json", context={REDIS_DUMP_FLAG_NAME: True}
        )
        await self.client_json.set(self.key, self.json_path, model_dump)  # type: ignore[misc]
        return self

    @mark_actions(ActionGroup.READ)
    async def aload(self):
        redis_value = await self.Meta.redis_json.get(self.key, self.field_path)  # type: ignore[misc]
        if redis_value is None:
            return None
        result = self._adapter.validate_python(
            redis_value, context={REDIS_DUMP_FLAG_NAME: True}
        )
        return result

    @abc.abstractmethod
    def clone(self):
        pass  # pragma: no cover

    @classmethod
    def redis_schema(cls, field_name: str):
        return TextField(f"$.{field_name}", as_name=field_name)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls, handler(cls.wrapped_python_type)
        )

    @staticmethod
    def serialize_unknown(value: Any):
        return base64.b64encode(pickle.dumps(value)).decode("utf-8")

    @staticmethod
    def deserialize_unknown(value: str):
        return pickle.loads(base64.b64decode(value))


def is_redis_field_value(value: Any) -> bool:
    # cheap isinstance(value, BaseRedisType): every instance sets _redis_updated in __init__
    return hasattr(value, "_redis_updated")
