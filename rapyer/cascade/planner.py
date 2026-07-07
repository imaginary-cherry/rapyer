from typing import Any, get_origin

from rapyer.types.relational import RelationalFieldType
from rapyer.utils.annotation import strip_optional
from rapyer.utils.pythonic import resolve_generic_args, safe_issubclass


def _unwrap_relational_target(annotation: Any) -> Any | None:
    """
    Resolve the ``AtomicRedisModel`` class an FK-shaped annotation points to,
    peeling ``Optional[...]`` and container wrappers (``list[...]``) along the
    way. Returns ``None`` when no relational type is reachable.
    """
    stripped = strip_optional(annotation)
    origin = get_origin(stripped) or stripped
    if safe_issubclass(origin, RelationalFieldType):
        args = resolve_generic_args(stripped)
        return args[0] if args else None
    for arg in resolve_generic_args(stripped):
        found = _unwrap_relational_target(arg)
        if found is not None:
            return found
    return None


class CascadePlanner:
    """
    Operation-agnostic FK-graph walker (EXT-01 extension seam): given a root
    key and class, ``atraverse`` follows every cascade-enabled edge
    cycle-safely to a per-subtree depth budget and returns a de-duplicated
    flat list of Redis keys, never hydrating a full model.

    ``field_attr``/``global_attr`` are parameterized so a future
    ``CascadeDelete`` strategy can reuse this exact class unmodified by
    pointing it at ``_cascade_delete_fields``/``Meta.cascade_delete``.
    """

    def __init__(
        self,
        field_attr: str = "_cascade_ttl_fields",
        global_attr: str = "cascade_ttl",
    ):
        self.field_attr = field_attr
        self.global_attr = global_attr

    def _next_hop(
        self,
        model_cls: Any,
        field_name: str,
        remaining_budget: int | None,
        established: bool,
    ) -> tuple[bool, int | None]:
        field_specs = getattr(model_cls, self.field_attr, {})
        field_spec = field_specs.get(field_name)
        if field_spec is not None:
            # D-09: an explicit per-field spec is a whole-object override — it
            # always wins and always REFRESHES the child's subtree budget,
            # regardless of any inherited remaining_budget (D-03 revised:
            # this is how a deeper field extends past a shallower ancestor).
            if not field_spec.enabled:
                return False, None
            return True, field_spec.depth

        global_spec = getattr(model_cls.Meta, self.global_attr, None)
        if global_spec is None or not global_spec.enabled:
            return False, None

        if not established:
            # D-01/D-03: first hop of a brand-new subtree via the blanket
            # global — the child's subtree budget is freshly set.
            return True, global_spec.depth

        # Continuing an already-established subtree purely via blanket
        # enable: decrement the inherited budget (D-05's visited-set remains
        # the real termination backstop; this is just the optional cap).
        if remaining_budget is None:
            return True, None
        if remaining_budget <= 0:
            return False, None
        return True, remaining_budget - 1

    def _resolve_target_cls(self, model_cls: Any, field_name: str) -> Any | None:
        annotation = model_cls.model_fields[field_name].annotation
        return _unwrap_relational_target(annotation)

    def _unwrap_nested_model_cls(self, annotation: Any) -> Any | None:
        """
        If ``annotation`` is itself an ``AtomicRedisModel`` subclass (D-06
        shape 3: a nested inline sub-model), return that class; else ``None``
        (D-06 shape 2: a collection-of-FK field). Both shapes currently land
        in the same ``_contain_fk`` classification set (RESEARCH.md Pitfall
        1) and must be re-disambiguated here, at traversal time.
        """
        # Imported lazily: rapyer.base already imports rapyer.cascade at
        # module level, so a top-level import here would create a cycle.
        from rapyer.base import AtomicRedisModel

        stripped = strip_optional(annotation)
        origin = get_origin(stripped) or stripped
        return origin if safe_issubclass(origin, AtomicRedisModel) else None

    def _walk_edges(
        self,
        model_cls: Any,
        dump: dict,
        remaining_budget: int | None,
        established: bool,
    ):
        """Yield ``(child_key, child_cls, new_budget)`` for every enabled, present edge."""
        for field_name in model_cls._relational_field_names:
            enabled, new_budget = self._next_hop(
                model_cls, field_name, remaining_budget, established
            )
            if not enabled:
                continue
            child_key = dump.get(field_name)
            if not child_key:
                continue
            target_cls = self._resolve_target_cls(model_cls, field_name)
            if target_cls is None:
                continue
            yield child_key, target_cls, new_budget

        for field_name in model_cls._contain_fk:
            annotation = model_cls.model_fields[field_name].annotation
            nested_cls = self._unwrap_nested_model_cls(annotation)
            if nested_cls is not None:
                # Shape 3: nested inline sub-model — same RedisJSON document,
                # zero-hop recursion. Never call _next_hop for the nesting
                # field itself; only the FK field(s) reached inside it.
                nested_dump = dump.get(field_name) or {}
                yield from self._walk_edges(
                    nested_cls, nested_dump, remaining_budget, established
                )
                continue

            # Shape 2: collection of FK — the marker lives on the collection
            # field itself; every element shares the same new_budget.
            enabled, new_budget = self._next_hop(
                model_cls, field_name, remaining_budget, established
            )
            if not enabled:
                continue
            target_cls = self._resolve_target_cls(model_cls, field_name)
            if target_cls is None:
                continue
            values = dump.get(field_name) or []
            iterable = values.values() if isinstance(values, dict) else values
            for child_key in iterable:
                if not child_key:
                    continue
                yield child_key, target_cls, new_budget

    async def _mget(self, entries: list[tuple[str, Any]]) -> dict[str, Any]:
        """
        Batch-read the raw JSON dump for every ``(key, cls)`` in ``entries``,
        grouped by ``Meta.redis_json`` client — one round trip per distinct
        client present at this BFS level (the common case is exactly one).
        """
        by_client: dict[Any, list[str]] = {}
        for key, cls in entries:
            by_client.setdefault(cls.Meta.redis_json, []).append(key)

        results: dict[str, Any] = {}
        for client, keys in by_client.items():
            dumps = await client.mget(keys=keys, path="$")
            for key, dump in zip(keys, dumps):
                results[key] = dump
        return results

    async def atraverse(self, root_key: str, root_cls: Any) -> list[str]:
        # CASC-04: the root key is visited before the first JSON.MGET, so a
        # self-reference/cycle back to the root can never double-collect it.
        visited: set[str] = {root_key}
        result: list[str] = list(root_cls._all_keys_for_key(root_key))
        frontier: list[tuple[str, Any, int | None, bool]] = [
            (root_key, root_cls, None, False)
        ]
        is_root_level = True

        while frontier:
            dumps = await self._mget([(key, cls) for key, cls, _, _ in frontier])
            next_frontier: list[tuple[str, Any, int | None, bool]] = []
            for key, cls, remaining_budget, established in frontier:
                dump = dumps.get(key)
                # Real redis returns None for a missing key; fakeredis returns [].
                if not dump:
                    # A dangling/missing node stops recursion here without
                    # raising; its own keyset was never added to the result
                    # (only the root's keyset is added unconditionally).
                    continue
                dump = dump[0] if isinstance(dump, list) else dump
                if not is_root_level:
                    # A non-root node's keyset is added only once its own
                    # JSON.MGET confirms it actually exists.
                    result.extend(cls._all_keys_for_key(key))
                for child_key, child_cls, new_budget in self._walk_edges(
                    cls, dump, remaining_budget, established
                ):
                    if not child_key or child_key in visited:
                        continue
                    visited.add(child_key)
                    next_frontier.append((child_key, child_cls, new_budget, True))
            frontier = next_frontier
            is_root_level = False

        return result


def _static_walk_fk_edges(
    planner: CascadePlanner, model_cls: Any, parent_path: str, fks: list[dict]
) -> None:
    """Append every enabled, static FK edge reachable from ``model_cls``'s own
    fields (shapes 1/2 directly, shape 3 by recursing into the nested
    sub-model) into ``fks``, mirroring ``CascadePlanner._walk_edges`` but
    without a runtime dump — each edge carries its OWN declared depth
    (field override else global else unbounded), not an inherited budget.
    """
    field_specs = getattr(model_cls, planner.field_attr, {})
    for field_name in model_cls._relational_field_names:
        enabled, depth = planner._next_hop(model_cls, field_name, None, False)
        if not enabled:
            continue
        target_cls = planner._resolve_target_cls(model_cls, field_name)
        if target_cls is None:
            continue
        edge = {
            "path": f"{parent_path}.{field_name}",
            "target": target_cls.__name__,
            "collection": False,
            "recurse": True,
            "ttl": True,
            "special": True,
            # WR-01: an enabled explicit per-field spec is a whole-object
            # override — the Lua traversal REFRESHES the child's budget to
            # this edge's depth (D-09 extend-past), never decrements it.
            # Without a field spec the edge is a blanket-global edge, which
            # decrements/caps the inherited budget instead.
            "override": field_specs.get(field_name) is not None,
        }
        if depth is not None:
            edge["depth"] = depth
        fks.append(edge)

    for field_name in model_cls._contain_fk:
        annotation = model_cls.model_fields[field_name].annotation
        nested_cls = planner._unwrap_nested_model_cls(annotation)
        if nested_cls is not None:
            # Shape 3: nested inline sub-model — same RedisJSON document,
            # zero-hop recursion; the marker lives on the nested class's own
            # field, so keep walking with model_cls=nested_cls.
            nested_path = f"{parent_path}.{field_name}"
            _static_walk_fk_edges(planner, nested_cls, nested_path, fks)
            continue

        # Shape 2: collection of FK — the marker lives on the collection
        # field itself; one edge covers every element.
        enabled, depth = planner._next_hop(model_cls, field_name, None, False)
        if not enabled:
            continue
        target_cls = planner._resolve_target_cls(model_cls, field_name)
        if target_cls is None:
            continue
        edge = {
            "path": f"{parent_path}.{field_name}",
            "target": target_cls.__name__,
            "collection": True,
            "recurse": True,
            "ttl": True,
            "special": True,
            # WR-01: see the shape-1 branch above — override vs blanket
            # decides refresh-vs-decrement in the Lua budget arithmetic.
            "override": field_specs.get(field_name) is not None,
        }
        if depth is not None:
            edge["depth"] = depth
        fks.append(edge)


def _static_walk_special_suffixes(model_cls: Any, parent_path: str = "") -> list[str]:
    """Derive the dotted-path ``special_suffixes`` for ``model_cls`` the same
    way ``AtomicRedisModel._all_keys_for_key`` walks ``_special_field_names``/
    ``_contain_sf`` (``rapyer/base.py``), stopping short of the model-key/
    prefix concatenation the Lua script applies itself.
    """
    suffixes: list[str] = []
    for field_name in model_cls._special_field_names:
        field_path = f"{parent_path}.{field_name}"
        suffixes.append(field_path.lstrip("."))
    for field_name in model_cls._contain_sf:
        field_cls = model_cls.model_fields[field_name].annotation
        if not hasattr(field_cls, "_special_field_names"):
            # _contain_sf also covers container-of-special-field shapes
            # (e.g. list[RedisSet]) whose annotation is a BaseRedisType
            # container, not an AtomicRedisModel — those have no per-class
            # suffix set to statically enumerate (same gap _all_keys_for_key
            # already has for this shape; out of this plan's scope).
            continue
        nested_path = f"{parent_path}.{field_name}"
        suffixes.extend(_static_walk_special_suffixes(field_cls, nested_path))
    return suffixes


def build_cascade_plan(models: list[type["AtomicRedisModel"]]) -> dict[str, dict]:
    """
    Build the static, per-class cascade plan table (D-02): every model in
    ``models`` gets exactly one entry keyed by its class name, covering all
    three D-06 FK shapes plus special-field-suffix derivation and the
    class's own ``Meta.ttl`` — the exact data shape the Lua cascade-apply
    script bakes in at ``SCRIPT LOAD``. Pure class/annotation introspection;
    never hydrates an instance or touches Redis.
    """
    planner = CascadePlanner()
    plan: dict[str, dict] = {}
    for model_cls in models:
        fks: list[dict] = []
        _static_walk_fk_edges(planner, model_cls, "$", fks)
        plan[model_cls.__name__] = {
            "ttl": model_cls.Meta.ttl,
            "special_suffixes": _static_walk_special_suffixes(model_cls),
            "fks": fks,
        }
    return plan


def validate_cascade_ttl_targets(plan: dict[str, dict]) -> None:
    """
    Raise ``CascadeTargetTtlMissingError`` (D-08) on the first cascade-enabled
    edge whose target class declares no ``Meta.ttl`` — a class never reached
    by any cascade-enabled edge is never required to declare one. Iterates
    deterministically in sorted-class-name, then list, order.
    """
    from rapyer.errors.cascade import CascadeTargetTtlMissingError

    for class_name, entry in sorted(plan.items()):
        for edge in entry["fks"]:
            target = edge["target"]
            if plan[target]["ttl"] is None:
                raise CascadeTargetTtlMissingError(
                    target,
                    f"{target!r} is reachable via a cascade-enabled edge "
                    f"from {class_name!r} (path {edge['path']!r}) but "
                    "declares no Meta.ttl",
                )
