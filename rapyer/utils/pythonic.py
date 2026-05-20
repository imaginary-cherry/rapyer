def safe_issubclass(cls, class_or_tuple):
    try:
        return issubclass(cls, class_or_tuple)
    except TypeError:
        return False


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
