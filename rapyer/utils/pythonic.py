def safe_issubclass(cls, class_or_tuple):
    try:
        return issubclass(cls, class_or_tuple)
    except TypeError:
        return False


def inject_at_paths(
    model_dump: dict,
    plan: list[tuple[str, ...]],
    raw_results: list,
):
    """
    Inject results from a pipeline into the model dump along the recorded paths.
    Each entry in ``plan`` is the path of one ``raw_results`` entry,
    in queue order. All entries belong to the same model dump (the caller that built the plan picked the key).
    """
    for path, raw in zip(plan, raw_results):
        target = model_dump
        for part in path[:-1]:
            target = target[part]
        target[path[-1]] = raw
