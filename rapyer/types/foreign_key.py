from typing import TYPE_CHECKING, Any, Generic, TypeVar, Union, get_args

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema

from rapyer.errors import NotResolvedError
from rapyer.types.relational import RelationalFieldType

if TYPE_CHECKING:
    from rapyer.base import AtomicRedisModel

T = TypeVar("T", bound="AtomicRedisModel")


class ForeignKey(RelationalFieldType, Generic[T]):
    """
    Typed, lazy reference to another ``AtomicRedisModel``.

    Stored inline in the parent's JSON as the target's Redis key string
    (e.g. ``"Author:abc-123"``). Construct from any of:
    """

    original_type: type = str
    _target_type_hint: Any = None

    def __init__(
        self,
        target_key: str | None = None,
        value: "AtomicRedisModel | None" = None,
    ):
        super().__init__()
        if value is not None:
            self._value = value
            self._target_key = target_key if target_key is not None else value.key
        else:
            self._value = None
            self._target_key = target_key

    def __class_getitem__(cls, item):
        parameterized = super().__class_getitem__(item)
        parameterized._target_type_hint = item
        return parameterized

    @property
    def target_key(self) -> str | None:
        return self._target_key

    @property
    def is_resolved(self) -> bool:
        return self._value is not None

    @property
    def value(self) -> "AtomicRedisModel":
        if self._value is None:
            raise NotResolvedError(
                f"ForeignKey to {self._target_key!r} is not resolved; "
                "call await fk.afetch() first."
            )
        return self._value

    async def afetch(self) -> "AtomicRedisModel":
        """Resolve the target instance from Redis and cache it in-place."""
        if self._value is not None:
            return self._value
        if self._target_key is None:
            raise NotResolvedError("ForeignKey has no target key to fetch.")
        target_cls = self._relational_target
        if target_cls is None:
            raise TypeError(
                f"{type(self).__name__} target type is unresolved; "
                "initialize rapyer (init_rapyer / resolve_forward_refs) and "
                "ensure the target is a registered AtomicRedisModel."
            )
        self._value = await target_cls.aget(self._target_key)
        return self._value

    async def aunload(self) -> None:
        """Drop the hydrated target instance; preserve the key reference."""
        self._value = None

    def __getattr__(self, name: str):
        """
        Delegate field access to the resolved target, e.g. ``fk.name``.

        Raises ``NotResolvedError`` until the target is fetched; never
        triggers I/O, since attribute access cannot await.
        """
        # __getattr__ only fires when normal lookup misses. Private/dunder
        # names (including during __init__ before _value is set) get the
        # standard AttributeError to avoid masking real errors and recursion.
        if name.startswith("_"):
            raise AttributeError(name)
        value = self.__dict__.get("_value")
        if value is None:
            raise NotResolvedError(
                f"ForeignKey to {self.__dict__.get('_target_key')!r} is not "
                f"resolved; call await fk.afetch() before accessing {name!r}."
            )
        return getattr(value, name)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ForeignKey):
            return self._target_key == other._target_key
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._target_key)

    def __repr__(self) -> str:
        state = "resolved" if self.is_resolved else "unresolved"
        return f"ForeignKey({self._target_key!r}, {state})"

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        args = get_args(source_type)
        target_hint = args[0] if args else cls._target_type_hint

        def _validate(value: Any) -> "ForeignKey":
            from rapyer.base import AtomicRedisModel

            if isinstance(value, ForeignKey):
                return value
            if isinstance(value, AtomicRedisModel):
                return cls(value=value)
            if isinstance(value, str):
                return cls(target_key=value)
            if isinstance(value, dict):
                # Beanie-style DBRef: {"$ref": "Author", "$id": "abc-123"}
                ref = value.get("$ref")
                pk = value.get("$id")
                if ref is not None and pk is not None:
                    return cls(target_key=f"{ref}:{pk}")
            raise TypeError(
                f"Cannot validate ForeignKey from {type(value).__name__}: {value!r}"
            )

        def _serialize(value: "ForeignKey") -> str | None:
            if value is None:
                return None
            return value._target_key

        # TODO: this name-normalization exists only because the metaclass converts a
        # Pin the generic parameter on the per-field subclass so the init-stage
        # resolver (resolve_relational_targets) can map it to the canonical
        # target model. Doesn't affect the schema itself.
        cls._target_type_hint = target_hint

        return core_schema.no_info_plain_validator_function(
            _validate,
            serialization=core_schema.plain_serializer_function_ser_schema(
                _serialize,
            ),
        )


if TYPE_CHECKING:
    # Field-declaration alias. To type checkers a reference field accepts the
    # target model, its key string, or an already-built ForeignKey, so assigning
    # any of them doesn't raise an annotation error. At runtime it is exactly
    # ``ForeignKey``, so pydantic builds the unchanged ForeignKey schema and the
    # stored value is always a ForeignKey (``isinstance(field, ForeignKey)``).
    Reference = Union[ForeignKey[T], T, str]
else:
    Reference = ForeignKey
