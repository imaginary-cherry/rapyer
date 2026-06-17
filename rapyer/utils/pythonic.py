from typing import TypeVar, get_args


def safe_issubclass(cls, class_or_tuple):
    try:
        return issubclass(cls, class_or_tuple)
    except TypeError:
        return False


def resolve_generic_args(type_) -> tuple:
    """
    Type args of a parameterized alias (``RedisList[str]``) or of a class that
    subclasses one, recovered from ``__orig_bases__`` (``class C(RedisList[str])``).
    """
    args = get_args(type_)
    if args:
        return args
    for base in getattr(type_, "__orig_bases__", ()):
        base_args = get_args(base)
        if base_args and not all(isinstance(a, TypeVar) for a in base_args):
            return base_args
    return ()


def inject_at_paths(model_dump: dict, plan: list[list[str]], raw_results: list):
    """
    Inject results from a pipeline into the model dump along the recorded paths.
    Each entry in ``plan`` is a list of field-name parts, e.g. ``["tags"]`` or
    ``["inner_set", "tags"]``.
    """
    for parts, raw in zip(plan, raw_results):
        target = model_dump
        for part in parts[:-1]:
            target = target[part]
        target[parts[-1]] = raw
