from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, get_origin

from rapyer.cascade.ttl import CascadeTTL
from rapyer.errors.cascade import CascadeTargetTtlMissingError
from rapyer.types.relational import RelationalFieldType
from rapyer.utils.annotation import strip_optional
from rapyer.utils.pythonic import resolve_generic_args, safe_issubclass

if TYPE_CHECKING:
    from rapyer.base import AtomicRedisModel


def _field_cascade_spec(model_cls: Any, field_name: str) -> CascadeTTL | None:
    """
    Read the explicit per-field ``CascadeTTL`` marker straight off pydantic's
    own field metadata (``model_cls.model_fields[field_name].metadata``) --
    pydantic already preserves this ``Annotated[...]`` metadata verbatim
    (including, for D-06 shape 3, inheriting it onto a nested-submodel
    wrapper's fields for free), so no separate class-level cache is needed.
    """
    field_info = model_cls.model_fields.get(field_name)
    if field_info is None:
        return None
    for metadata in field_info.metadata:
        if isinstance(metadata, CascadeTTL):
            return metadata
    return None


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


@dataclass(frozen=True)
class CascadeEdge:
    """
    One FK edge out of a class in the cascade plan table. ``depth=None`` means
    unbounded; ``_lua_literal`` (``rapyer/scripts/registry.py``) omits
    ``None``-valued fields, so the Lua table never carries a literal ``depth``
    key for these.
    """

    path: str
    target: str
    collection: bool
    recurse: bool
    ttl: bool
    special: bool
    override: bool
    depth: int | None = None


@dataclass(frozen=True)
class CascadePlanEntry:
    """One class's full entry in the cascade plan table."""

    ttl: int | None
    special_suffixes: list[str]
    fks: list[CascadeEdge]


def _classify_edge(model_cls: Any, field_name: str) -> tuple[bool, int | None, bool]:
    """
    Single-hop static classification of one FK-shaped field on ``model_cls``:
    field-spec override else global blanket else disabled. Returns
    ``(enabled, depth, override)``. Carries no budget accounting -- all
    multi-hop decrement/refresh bookkeeping lives entirely in the Lua
    ``cascade_ttl_apply`` script's own ``next_hop``.
    """
    field_spec = _field_cascade_spec(model_cls, field_name)
    if field_spec is not None:
        if not field_spec.enabled:
            return False, None, True
        return True, field_spec.depth, True

    global_spec = getattr(model_cls.Meta, "cascade_ttl", None)
    if global_spec is None or not global_spec.enabled:
        return False, None, False
    return True, global_spec.depth, False


def _resolve_target_cls(model_cls: Any, field_name: str) -> Any | None:
    annotation = model_cls.model_fields[field_name].annotation
    return _unwrap_relational_target(annotation)


def _unwrap_nested_model_cls(annotation: Any) -> Any | None:
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


def _static_walk_fk_edges(
    model_cls: Any, parent_path: str, fks: list[CascadeEdge]
) -> None:
    """Append every enabled, static FK edge reachable from ``model_cls``'s own
    fields (shapes 1/2 directly, shape 3 by recursing into the nested
    sub-model) into ``fks`` — performs the same shape-1/2/3 static edge
    classification (no runtime dump involved), each edge carrying its OWN
    declared depth (field override else global else unbounded), not an
    inherited budget.
    """
    for field_name in model_cls._relational_field_names:
        enabled, depth, override = _classify_edge(model_cls, field_name)
        if not enabled:
            continue
        target_cls = _resolve_target_cls(model_cls, field_name)
        if target_cls is None:
            continue
        # WR-01: an enabled explicit per-field spec is a whole-object
        # override — the Lua traversal REFRESHES the child's budget to
        # this edge's depth (D-09 extend-past), never decrements it.
        # Without a field spec the edge is a blanket-global edge, which
        # decrements/caps the inherited budget instead.
        fks.append(
            CascadeEdge(
                path=f"{parent_path}.{field_name}",
                target=target_cls.__name__,
                collection=False,
                recurse=True,
                ttl=True,
                special=True,
                override=override,
                depth=depth,
            )
        )

    for field_name in model_cls._contain_fk:
        annotation = model_cls.model_fields[field_name].annotation
        nested_cls = _unwrap_nested_model_cls(annotation)
        if nested_cls is not None:
            # Shape 3: nested inline sub-model — same RedisJSON document,
            # zero-hop recursion; the marker lives on the nested class's own
            # field, so keep walking with model_cls=nested_cls.
            nested_path = f"{parent_path}.{field_name}"
            _static_walk_fk_edges(nested_cls, nested_path, fks)
            continue

        # Shape 2: collection of FK — the marker lives on the collection
        # field itself; one edge covers every element.
        enabled, depth, override = _classify_edge(model_cls, field_name)
        if not enabled:
            continue
        target_cls = _resolve_target_cls(model_cls, field_name)
        if target_cls is None:
            continue
        # WR-01: see the shape-1 branch above — override vs blanket
        # decides refresh-vs-decrement in the Lua budget arithmetic.
        fks.append(
            CascadeEdge(
                path=f"{parent_path}.{field_name}",
                target=target_cls.__name__,
                collection=True,
                recurse=True,
                ttl=True,
                special=True,
                override=override,
                depth=depth,
            )
        )


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


def build_cascade_plan(
    models: list[type["AtomicRedisModel"]],
) -> dict[str, CascadePlanEntry]:
    """
    Build the static, per-class cascade plan table (D-02): every model in
    ``models`` gets exactly one entry keyed by its class name, covering all
    three D-06 FK shapes plus special-field-suffix derivation and the
    class's own ``Meta.ttl`` — the exact data shape the Lua cascade-apply
    script bakes in at ``SCRIPT LOAD``. Pure class/annotation introspection;
    never hydrates an instance or touches Redis.
    """
    plan: dict[str, CascadePlanEntry] = {}
    for model_cls in models:
        fks: list[CascadeEdge] = []
        _static_walk_fk_edges(model_cls, "$", fks)
        plan[model_cls.__name__] = CascadePlanEntry(
            ttl=model_cls.Meta.ttl,
            special_suffixes=_static_walk_special_suffixes(model_cls),
            fks=fks,
        )
    return plan


def validate_cascade_ttl_targets(plan: dict[str, CascadePlanEntry]) -> None:
    """
    Raise ``CascadeTargetTtlMissingError`` (D-08) whenever a class that
    participates in a cascade lacks a ``Meta.ttl``. The Lua write phase EXPIREs
    every key with its OWNING class's baked-in ttl, so a ``None`` ttl becomes a
    nil-arg Lua runtime error. Two cases are enforced:

    - a cascade-enabled edge TARGET refreshes the target's own key (checked
      first, preserving the original D-08 first-violation ordering);
    - a cascade ROOT — any class with outgoing cascade-enabled edges (WR-02) —
      also refreshes its OWN key, so it too must declare a ttl.

    Both passes iterate deterministically in sorted-class-name, then list order.
    """
    for class_name, entry in sorted(plan.items()):
        for edge in entry.fks:
            target = edge.target
            # WR-03: a partial plan (built from a subset of models) may omit an
            # edge's target entirely — surface a RapyerError, never a bare
            # KeyError, per the "all library errors inherit RapyerError" rule.
            target_entry = plan.get(target)
            if target_entry is None:
                raise CascadeTargetTtlMissingError(
                    target,
                    f"{target!r} is reachable via a cascade-enabled edge from "
                    f"{class_name!r} (path {edge.path!r}) but is absent from "
                    "the cascade plan",
                )
            if target_entry.ttl is None:
                raise CascadeTargetTtlMissingError(
                    target,
                    f"{target!r} is reachable via a cascade-enabled edge "
                    f"from {class_name!r} (path {edge.path!r}) but "
                    "declares no Meta.ttl",
                )

    # WR-02: a cascade root refreshes its own key too, so a class with outgoing
    # cascade-enabled edges but no Meta.ttl is just as fatal as a target with no
    # ttl. Checked in a second pass so an edge-target violation (above) always
    # takes precedence, keeping the original first-violation ordering stable.
    for class_name, entry in sorted(plan.items()):
        if entry.fks and entry.ttl is None:
            raise CascadeTargetTtlMissingError(
                class_name,
                f"{class_name!r} has outgoing cascade-enabled edges (it is a "
                "cascade root) but declares no Meta.ttl; the cascade would "
                "EXPIRE its own key with a nil ttl",
            )
