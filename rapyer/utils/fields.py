from typing import get_origin, ClassVar

from pydantic import BaseModel, TypeAdapter
from pydantic.fields import FieldInfo


def _collect_annotations_recursive(
    current_cls: type[BaseModel],
    base_class: type[BaseModel],
    visited: set[type[BaseModel]],
) -> dict[str, FieldInfo]:
    """
    Helper functions to recursively collect annotations.

    Args:
        current_cls: Current class being processed
        base_class: The base class, all class we can ignore all fields from a class who inherit from this class
        visited: Set of already visited classes
    """
    all_annotations = {}
    # Avoid infinite loops
    if current_cls in visited:
        return {}
    visited.add(current_cls)

    # First, recursively process parent classes
    for base in current_cls.__bases__:
        # Skip object class
        if base is object:
            continue
        if not issubclass(base, BaseModel):
            continue
        # If this class already inherits from the base class, the fields are already collected
        if issubclass(base, base_class):
            continue
        new_annotation = _collect_annotations_recursive(base, base_class, visited)
        all_annotations.update(new_annotation)

    if not issubclass(current_cls, base_class):
        all_annotations.update(current_cls.model_fields)
    return all_annotations


def get_all_pydantic_annotation(
    cls: type[BaseModel], exclude_classes: type[BaseModel] = None
) -> dict[str, FieldInfo]:
    """
    Recursively get all annotations from a class and its parent classes.
    Excludes private fields (starting with _) and ClassVar annotations.

    Returns:
        dict: Merged annotations from the class hierarchy
    """
    visited = set()

    return _collect_annotations_recursive(cls, exclude_classes, visited)


def is_redis_field(field_name, field_annotation):
    return not (
        field_name.startswith("_")
        or field_name.endswith("_")
        or get_origin(field_annotation) is ClassVar
    )


def is_type_dumpable(typ: type) -> bool:
    return False
    try:
        TypeAdapter(typ).json_schema()
        return True
    except Exception:
        return False
