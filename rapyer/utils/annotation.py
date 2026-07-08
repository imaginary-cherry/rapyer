import abc
from abc import ABC
from types import UnionType
from typing import Annotated, Any, Union, get_args, get_origin

from rapyer.types.relational import RelationalFieldType
from rapyer.utils.pythonic import safe_issubclass

DYNAMIC_CLASS_DOC = "___dynamic_class___"


class TypeConverter(ABC):
    @abc.abstractmethod
    def is_type_support(self, type_to_check: type) -> bool:
        pass  # pragma: no cover

    @abc.abstractmethod
    def convert_flat_type(self, type_to_convert: type) -> type:
        pass  # pragma: no cover

    @abc.abstractmethod
    def covert_generic_type(
        self, type_to_covert: type, generic_values: tuple[type]
    ) -> type:
        pass  # pragma: no cover


def replace_to_redis_types_in_annotation(
    annotation: Any, type_converter: TypeConverter
) -> Any:
    """
    Recursively traverse a type annotation and replace types according to the mapping.
    Handles Union, Optional, Annotated, and other generic types.
    """
    # Relational field is not dynamically created, it stays simple field
    if safe_issubclass(get_origin(annotation) or annotation, RelationalFieldType):
        return annotation

    # Direct type replacement
    if type_converter.is_type_support(annotation):
        new_type = type_converter.convert_flat_type(annotation)
        return new_type

    origin = get_origin(annotation)
    args = get_args(annotation)

    # If no origin, it's a simple type (already checked mapping above)
    if origin is None:
        return annotation

    # Handle Annotated specially - preserve metadata
    if origin is Annotated:
        # The first arg is the actual type, rest are metadata
        actual_type = args[0]
        metadata = args[1:]

        # Recursively replace the actual type
        new_type = replace_to_redis_types_in_annotation(actual_type, type_converter)

        # Reconstruct Annotated with new type and original metadata
        annotated_args = (new_type,) + metadata
        return Annotated[annotated_args]

    # Handle Union, Optional, and other generic types
    if args:
        # Recursively replace types in all arguments
        new_args = tuple(
            [replace_to_redis_types_in_annotation(arg, type_converter) for arg in args]
        )

        # Reconstruct the generic type with new arguments
        if type_converter.is_type_support(origin):
            origin = type_converter.covert_generic_type(origin, new_args)
        elif origin is UnionType:
            origin = Union[new_args]
        # This is for optional support
        elif origin is Union:
            origin = Union[new_args]
        else:
            # If we don't support the origin, just use the original annotation
            origin = annotation
        return origin
    return annotation  # pragma: no cover - There is no way to reach this line


def strip_optional(annotation: Any) -> Any:
    """Peel a ``Union[X, None]`` / ``X | None`` wrapper down to ``X``."""
    if get_origin(annotation) in (Union, UnionType):
        non_none = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(non_none) == 1:
            return non_none[0]
    return annotation


def annotation_origin(annotation: Any) -> Any:
    """Peel ``Annotated`` and ``Optional`` wrappers and return the underlying origin type."""
    unwrapped = annotation
    while get_origin(unwrapped) is Annotated:
        unwrapped = get_args(unwrapped)[0]
    unwrapped = strip_optional(unwrapped)
    return get_origin(unwrapped) or unwrapped


def has_annotation(field: Any, annotation_type: Any) -> bool:
    origin = get_origin(field)
    if origin is Annotated:
        args = get_args(field)
        # Check metadata for annotation_type instances
        for metadata in args[1:]:
            if isinstance(metadata, annotation_type):
                return True

    return False


def field_with_flag(field, flag):
    return any([isinstance(metadata, flag) for metadata in field.metadata])
