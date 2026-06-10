from typing import TYPE_CHECKING, Any, Generic, TypeVar, Union, get_args

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema

from rapyer.actions import ActionGroup, TargetSource, mark_actions
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

    def __init__(self, ref: "str | AtomicRedisModel"):
        super().__init__()
        if isinstance(ref, str):
            # A Redis key string — the reference stays unresolved until afetch.
            self._value = None
            self._target_key = ref
        else:
            # Anything else is assumed to be the target AtomicRedisModel.
            self._value = ref
            self._target_key = ref.key

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

    @mark_actions(ActionGroup.READ, ActionGroup.FETCH, target=TargetSource.RESULT)
    async def afetch(self) -> "AtomicRedisModel":
        """Resolve the target instance from Redis and cache it in-place."""
        if self._value is not None:
            return self._value
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
            if isinstance(value, (AtomicRedisModel, str)):
                # __init__ dispatches: a str is a key, a model is the target.
                return cls(value)
            if isinstance(value, dict):
                # Beanie-style DBRef: {"$ref": "Author", "$id": "abc-123"}
                ref = value.get("$ref")
                pk = value.get("$id")
                if ref is not None and pk is not None:
                    return cls(f"{ref}:{pk}")
            raise TypeError(
                f"Cannot validate ForeignKey from {type(value).__name__}: {value!r}"
            )

        def _serialize(value: "ForeignKey") -> str | None:
            if value is None:
                return None
            return value._target_key

        # TODO: this name-normalization exists only because the metaclass converts a
        #       ForeignKey's target into a dynamic per-field subclass. Once reference
        #       targets are kept as static types, this can be removed (or reduced to a thin
        #       forward-ref-string fallback).
        #       https://github.com/imaginary-cherry/rapyer/issues/247
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
