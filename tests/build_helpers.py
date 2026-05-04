"""Test/benchmark helpers for rebuilding redis models after mutating ``Meta``.

The model class's own ``build_redis_model`` only re-installs marked-action
methods on the model class itself. Per-field ``BaseRedisType`` subclasses are
specialized once (in their ``__init_subclass__``) against the owning model's
``Meta`` snapshot at class-definition time, so they don't pick up later
mutations to ``Meta.ttl`` / ``Meta.refresh_ttl``.

``recursive_build_redis_model`` walks the fields and rebuilds every dynamic
``BaseRedisType`` subclass with the model's current ``Meta``. It's intentionally
test-side (not in the runtime path) — production code should set ``Meta`` at
class-definition time.

Caller responsibility: the helper walks **all** fields including inherited
ones. When two classes in an inheritance hierarchy share a per-field subclass
and have diverging ``Meta``, only call this on the field-owning class.
"""

from typing import get_args, get_origin

from rapyer.base import AtomicRedisModel
from rapyer.types.base import BaseRedisType


def _iter_annotation_types(annotation):
    if isinstance(annotation, type):
        yield annotation
    origin = get_origin(annotation)
    if isinstance(origin, type):
        yield origin
    for arg in get_args(annotation):
        yield from _iter_annotation_types(arg)


def recursive_build_redis_model(cls: type[AtomicRedisModel]):
    """Rebuild ``cls`` and its dynamic per-field ``BaseRedisType`` subclasses."""
    cls.build_redis_model()
    seen: set[int] = set()
    for field_info in cls.model_fields.values():
        for t in _iter_annotation_types(field_info.annotation):
            if id(t) in seen:
                continue
            seen.add(id(t))
            if issubclass(t, BaseRedisType):
                t.build_redis_model(cls.Meta)
