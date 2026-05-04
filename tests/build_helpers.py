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


def recursive_build_redis_model(
    cls: type[AtomicRedisModel],
    _seen: set[int] | None = None,
):
    """Rebuild ``cls``, its per-field ``BaseRedisType`` subclasses, and any
    nested ``AtomicRedisModel`` fields (each rebuilt against its own ``Meta``).
    """
    if _seen is None:
        _seen = set()
    if id(cls) in _seen:
        return
    _seen.add(id(cls))

    cls.build_redis_model()
    for field_info in cls.model_fields.values():
        for t in _iter_annotation_types(field_info.annotation):
            if id(t) in _seen:
                continue
            if issubclass(t, BaseRedisType):
                _seen.add(id(t))
                t.build_redis_model(cls.Meta)
            elif issubclass(t, AtomicRedisModel):
                # Nested model — recurse with its own Meta. Don't mark it
                # ``_seen`` here; the recursive call does that to also block
                # re-entry from inside the nested walk.
                recursive_build_redis_model(t, _seen)
