import dataclasses
import hashlib
import json
from typing import TYPE_CHECKING, Any, get_origin

from rapyer.cascade.ttl import CascadeTTL
from rapyer.errors.cascade import CascadeLuaLiteralError, CascadeTargetTtlMissingError
from rapyer.scripts.constants import CASCADE_FUNCTION_PREFIX, CASCADE_LIBRARY_PREFIX
from rapyer.types.relational import RelationalFieldType
from rapyer.utils.annotation import strip_optional
from rapyer.utils.pythonic import resolve_generic_args, safe_issubclass

if TYPE_CHECKING:
    from rapyer.base import AtomicRedisModel


def _field_cascade_spec(model_cls: Any, field_name: str) -> CascadeTTL | None:
    """Return the per-field CascadeTTL marker from the field's annotation metadata."""
    field_info = model_cls.model_fields.get(field_name)
    if field_info is None:
        return None
    for metadata in field_info.metadata:
        if isinstance(metadata, CascadeTTL):
            return metadata
    return None


def _unwrap_relational_target(annotation: Any) -> Any | None:
    """Return the model class an FK-shaped annotation points to, or None."""
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


@dataclasses.dataclass(frozen=True)
class CascadeEdge:
    """
    One FK edge out of a class in the cascade plan table.

    depth=None means unbounded; cascade_plan_json drops None-valued fields, so
    the per-call plan JSON carries no depth key for these.

    recurse_into_target / refresh_target_ttl / refresh_target_special_keys are
    always True today: every edge the planner currently emits follows the
    target, refreshes its ttl, and refreshes its special keys. They are
    forward-looking per-edge hooks for future delete/save-cascade work — the
    Lua keeps a documented dead branch for the non-recursing case so it is
    ready when a planner-side reason to set them False shows up.
    resets_depth_budget means an explicit per-field CascadeTTL() spec resets
    the child's depth budget to this edge's own depth instead of decrementing
    the budget inherited from the parent.
    """

    path: str
    target: str
    is_collection: bool
    recurse_into_target: bool
    refresh_target_ttl: bool
    refresh_target_special_keys: bool
    resets_depth_budget: bool
    depth: int | None = None


@dataclasses.dataclass(frozen=True)
class CascadePlanEntry:
    """One class's full entry in the cascade plan table."""

    ttl: int | None
    # Special fields live under their own Redis key (SF: RedisSet,
    # RedisPriorityQueue), separate from the main JSON document; the Lua must
    # EXPIRE each of these suffixed keys alongside the main key whenever it
    # refreshes this class's key.
    special_suffixes: list[str]
    fks: list[CascadeEdge]


@dataclasses.dataclass(frozen=True)
class EdgeClassification:
    """
    Result of classifying a single FK-shaped field: enabled, its depth, and
    whether an explicit per-field spec overrode the global default.
    """

    enabled: bool
    depth: int | None
    override: bool


def _classify_edge(model_cls: Any, field_name: str) -> EdgeClassification:
    """Classify one FK field: per-field spec overrides the global blanket spec."""
    field_spec = _field_cascade_spec(model_cls, field_name)
    if field_spec is not None:
        if not field_spec.enabled:
            return EdgeClassification(enabled=False, depth=None, override=True)
        return EdgeClassification(enabled=True, depth=field_spec.depth, override=True)

    global_spec = getattr(model_cls.Meta, "cascade_ttl", None)
    if global_spec is None or not global_spec.enabled:
        return EdgeClassification(enabled=False, depth=None, override=False)
    return EdgeClassification(enabled=True, depth=global_spec.depth, override=False)


def _resolve_target_cls(model_cls: Any, field_name: str) -> Any | None:
    annotation = model_cls.model_fields[field_name].annotation
    return _unwrap_relational_target(annotation)


def _unwrap_nested_model_cls(annotation: Any) -> Any | None:
    """Return the class if annotation is a nested inline sub-model, else None."""
    # Lazy import: rapyer.base imports rapyer.cascade at module level, so a
    # top-level import here would create a cycle.
    from rapyer.base import AtomicRedisModel

    stripped = strip_optional(annotation)
    origin = get_origin(stripped) or stripped
    return origin if safe_issubclass(origin, AtomicRedisModel) else None


def _static_walk_fk_edges(model_cls: Any, parent_path: str, fks: list[CascadeEdge]):
    """
    Append every enabled FK edge reachable from model_cls's own fields.

    Direct and collection FK fields become edges here; nested inline sub-models
    are walked recursively. Each edge carries its own declared depth (field
    override else global else unbounded).
    """
    for field_name in model_cls._relational_field_names:
        edge = _classify_edge(model_cls, field_name)
        if not edge.enabled:
            continue
        target_cls = _resolve_target_cls(model_cls, field_name)
        if target_cls is None:
            continue
        # An explicit per-field spec is a whole-object override: the Lua
        # traversal refreshes the child's budget to this edge's depth. A blanket
        # global edge decrements/caps the inherited budget instead.
        fks.append(
            CascadeEdge(
                path=f"{parent_path}.{field_name}",
                target=target_cls.__name__,
                is_collection=False,
                recurse_into_target=True,
                refresh_target_ttl=True,
                refresh_target_special_keys=True,
                resets_depth_budget=edge.override,
                depth=edge.depth,
            )
        )

    for field_name in model_cls._contain_fk:
        annotation = model_cls.model_fields[field_name].annotation
        nested_cls = _unwrap_nested_model_cls(annotation)
        if nested_cls is not None:
            # Nested inline sub-model: same RedisJSON document, zero-hop
            # recursion; the marker lives on the nested class's own field.
            nested_path = f"{parent_path}.{field_name}"
            _static_walk_fk_edges(nested_cls, nested_path, fks)
            continue

        # Collection of FK: the marker lives on the collection field itself;
        # one edge covers every element.
        edge = _classify_edge(model_cls, field_name)
        if not edge.enabled:
            continue
        target_cls = _resolve_target_cls(model_cls, field_name)
        if target_cls is None:
            continue
        fks.append(
            CascadeEdge(
                path=f"{parent_path}.{field_name}",
                target=target_cls.__name__,
                is_collection=True,
                recurse_into_target=True,
                refresh_target_ttl=True,
                refresh_target_special_keys=True,
                resets_depth_budget=edge.override,
                depth=edge.depth,
            )
        )


def _static_walk_special_suffixes(model_cls: Any, parent_path: str = "") -> list[str]:
    """
    Derive the dotted-path special-field suffixes for model_cls, recursing
    into nested sub-models that themselves hold special fields.
    """
    from rapyer.base import AtomicRedisModel

    suffixes: list[str] = []
    for field_name in model_cls._special_field_names:
        field_path = f"{parent_path}.{field_name}"
        suffixes.append(field_path.lstrip("."))
    for field_name in model_cls._contain_sf:
        annotation = model_cls.model_fields[field_name].annotation
        # Unwrap Optional[...]/generic origins the same way
        # _unwrap_nested_model_cls does, so a nested model hidden behind
        # Optional[...] or a generic alias is still recognized.
        stripped = strip_optional(annotation)
        field_cls = get_origin(stripped) or stripped
        # Container-of-special-field shapes (e.g. list[RedisSet]) have no
        # per-class suffix set to enumerate; only nested models with their own
        # special fields do.
        if not safe_issubclass(field_cls, AtomicRedisModel):
            continue
        if not field_cls.contains_sf_field():
            continue
        nested_path = f"{parent_path}.{field_name}"
        suffixes.extend(_static_walk_special_suffixes(field_cls, nested_path))
    return suffixes


def build_cascade_plan(
    models: list[type["AtomicRedisModel"]],
) -> dict[str, CascadePlanEntry]:
    """
    Build the static, per-class cascade plan table baked into the Lua script.

    Every model gets one entry keyed by its class name, covering its FK edges,
    special-field suffixes, and own Meta.ttl. Pure annotation introspection;
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


def validate_cascade_ttl_targets(plan: dict[str, CascadePlanEntry]):
    """
    Raise CascadeTargetTtlMissingError when a cascade participant lacks a ttl.

    The Lua write phase EXPIREs every reached key with its owning class's ttl, so
    a None ttl would become a nil-arg runtime error. Both an edge's target and a
    cascade root (a class with outgoing edges) refresh their own key and so must
    declare a ttl. Target violations are checked first to keep a stable,
    deterministic first-violation order.
    """
    for class_name, entry in sorted(plan.items()):
        for edge in entry.fks:
            target = edge.target
            # A partial plan (a subset of models) may omit an edge's target;
            # surface a RapyerError rather than a bare KeyError.
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

    for class_name, entry in sorted(plan.items()):
        if entry.fks and entry.ttl is None:
            raise CascadeTargetTtlMissingError(
                class_name,
                f"{class_name!r} has outgoing cascade-enabled edges (it is a "
                "cascade root) but declares no Meta.ttl; the cascade would "
                "EXPIRE its own key with a nil ttl",
            )


def _drop_none_values(value: Any) -> Any:
    """Recursively drop None-valued dict keys (depth/ttl omitted when unset)."""
    if isinstance(value, dict):
        return {
            key: _drop_none_values(inner)
            for key, inner in value.items()
            if inner is not None
        }
    if isinstance(value, list):
        return [_drop_none_values(item) for item in value]
    return value


def cascade_plan_json(plan: dict[str, CascadePlanEntry]) -> str:
    """
    Serialize the full cascade plan to compact JSON.

    The result is written once to a Redis key at init_rapyer and read
    server-side by the Lua on every call, rather than shipped per call.
    """
    payload = {
        name: _drop_none_values(dataclasses.asdict(entry))
        for name, entry in plan.items()
    }
    return json.dumps(payload, separators=(",", ":"))


def cascade_plan_hash(plan_json: str) -> str:
    """Short, stable hex digest of a compact plan JSON; deterministic across processes."""
    return hashlib.sha1(plan_json.encode()).hexdigest()[:16]  # nosec B324


def cascade_names(plan_json: str) -> tuple[str, str]:
    """Deterministic (library_name, function_name) for a plan, both carrying the plan hash."""
    # Redis Function NAMES are server-GLOBAL, not per-library: two libraries
    # cannot both register a function named "cascade_apply" (the second FUNCTION
    # LOAD errors). Baking the plan hash into BOTH the library AND the function
    # name lets two rapyer processes with different model sets (e.g. CI workers)
    # coexist on one server instead of clobbering each other's baked plan;
    # identical plans hash-collide to the same names so FUNCTION LOAD REPLACE is
    # idempotent. FCALL therefore targets the hashed function name.
    plan_hash = cascade_plan_hash(plan_json)
    return (
        f"{CASCADE_LIBRARY_PREFIX}_{plan_hash}",
        f"{CASCADE_FUNCTION_PREFIX}_{plan_hash}",
    )


def cascade_plan_lua_literal(plan_json: str) -> str:
    """Wrap the compact plan JSON in a Lua long-bracket literal so it embeds verbatim."""
    # The plan JSON is identifier/path/suffix data only (class names, dotted
    # $-paths, special-field suffixes) — none can contain ]==]. Guard anyway
    # rather than trust that invariant, since this bakes into executable source.
    if "]==]" in plan_json:
        raise CascadeLuaLiteralError(
            "cascade plan JSON contains the Lua long-bracket delimiter ']==]', "
            "which would break out of the embedded literal"
        )
    return f"[==[{plan_json}]==]"
