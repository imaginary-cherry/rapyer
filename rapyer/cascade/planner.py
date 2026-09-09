import dataclasses
import hashlib
import json
from typing import TYPE_CHECKING, Annotated, Any

from rapyer.cascade.spec import CascadeSpec
from rapyer.errors.cascade import (
    CascadeKeyInitialsError,
    CascadeLuaLiteralError,
    CascadeTargetTtlMissingError,
)
from rapyer.scripts.constants import CASCADE_FUNCTION_PREFIX, CASCADE_LIBRARY_PREFIX
from rapyer.types.foreign_key import ForeignKey
from rapyer.types.relational import RelationalFieldType
from rapyer.types.traits import FieldTrait
from rapyer.utils.pythonic import safe_issubclass

if TYPE_CHECKING:
    from rapyer.base import AtomicRedisModel


def _field_cascade_spec(model_cls: Any, field_name: str) -> CascadeSpec | None:
    """Return the per-field cascade config from the field's Annotated metadata."""
    field_info = model_cls.model_fields.get(field_name)
    if field_info is None:
        return None
    annotation = field_info.annotation
    if field_info.metadata:
        annotation = Annotated[(annotation, *field_info.metadata)]
    spec = model_cls._field_specs.get(field_name)
    is_relational = (
        spec is not None
        and spec.external is not None
        and spec.external.field_type.traits() & FieldTrait.REFERENCES_ROOT
    )
    field_type = spec.external.field_type if is_relational else ForeignKey
    return field_type.extract_config(annotation)


@dataclasses.dataclass(frozen=True)
class CascadeEdge:
    """One FK edge out of a class in the cascade plan table."""

    path: str
    target: str
    is_collection: bool
    # Always True today; forward-looking hooks for future delete/save-cascade work.
    recurse_into_target: bool
    refresh_target_ttl: bool
    refresh_target_special_keys: bool
    # A per-field CascadeTTL() resets the child's budget to this depth, not decrement the parent's.
    resets_depth_budget: bool
    # None means unbounded; cascade_plan_json drops it from the per-call JSON.
    depth: int | None = None
    # None = inline; "set"/"zset" = FK held in a RedisSet/PQ, path is then the SF key suffix.
    sf_container: str | None = None
    # Class names a union/polymorphic edge may reach; None keeps single-target JSON identical.
    candidates: list[str] | None = None


@dataclasses.dataclass(frozen=True)
class CascadePlanEntry:
    """One class's full entry in the cascade plan table."""

    ttl: int | None
    # SF keys (RedisSet/PQ) live under their own suffixed keys, EXPIREd alongside the main key.
    special_suffixes: list[str]
    fks: list[CascadeEdge]


@dataclasses.dataclass(frozen=True)
class EdgeClassification:
    """Whether an FK field cascades, its depth, and if a per-field spec overrode the global."""

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


def _resolve_target_cls(
    model_cls: Any, field_name: str, models: list[type["AtomicRedisModel"]]
) -> list[type["AtomicRedisModel"]]:
    annotation = model_cls.model_fields[field_name].annotation
    return RelationalFieldType.relational_targets(annotation, models)


def _static_walk_fk_edges(
    model_cls: Any,
    parent_path: str,
    fks: list[CascadeEdge],
    models: list[type["AtomicRedisModel"]],
    top_level: bool = True,
):
    """Append every enabled FK edge reachable from model_cls's own fields."""
    # Lazy import breaks the rapyer.base -> rapyer.cascade module cycle.
    from rapyer.base import AtomicRedisModel

    for field_name, spec in model_cls._field_specs.items():
        if not (
            spec.external is not None
            and spec.external.field_type.traits() & FieldTrait.REFERENCES_ROOT
        ):
            continue
        edge = _classify_edge(model_cls, field_name)
        if not edge.enabled:
            continue
        cands = _resolve_target_cls(model_cls, field_name, models)
        if not cands:
            continue
        # A per-field spec resets the child's budget to this depth; a global edge decrements it.
        fks.append(
            CascadeEdge(
                path=f"{parent_path}.{field_name}",
                target=cands[0].__name__,
                is_collection=False,
                recurse_into_target=True,
                refresh_target_ttl=True,
                refresh_target_special_keys=True,
                resets_depth_budget=edge.override,
                depth=edge.depth,
                candidates=([c.__name__ for c in cands] if len(cands) > 1 else None),
            )
        )

    for field_name, spec in model_cls._field_specs.items():
        if not spec.reaches & FieldTrait.REFERENCES_ROOT:
            continue
        field_cls = spec.field_type
        if safe_issubclass(field_cls, AtomicRedisModel):
            # Nested inline sub-model: same RedisJSON document, zero-hop recursion.
            nested_path = f"{parent_path}.{field_name}"
            _static_walk_fk_edges(field_cls, nested_path, fks, models, top_level=False)
            continue

        # Lazy import: priority_queue -> special -> scripts.loader -> planner is a real cycle.
        from rapyer.types.special import SpecialFieldType

        sf_container = (
            field_cls.cascade_container_kind()
            if safe_issubclass(field_cls, SpecialFieldType)
            else None
        )
        if sf_container is not None:
            # Nested SF-held-ref traversal is deferred; direct fields only.
            if not top_level:
                continue
            edge = _classify_edge(model_cls, field_name)
            if not edge.enabled:
                continue
            annotation = model_cls.model_fields[field_name].annotation
            cands = RelationalFieldType.relational_targets(annotation, models)
            if not cands:
                continue
            fks.append(
                CascadeEdge(
                    path=field_name,
                    target=cands[0].__name__,
                    is_collection=True,
                    recurse_into_target=True,
                    refresh_target_ttl=True,
                    refresh_target_special_keys=True,
                    resets_depth_budget=edge.override,
                    depth=edge.depth,
                    sf_container=sf_container,
                    candidates=(
                        [c.__name__ for c in cands] if len(cands) > 1 else None
                    ),
                )
            )
            continue

        # Collection of FK: one edge covers every element.
        edge = _classify_edge(model_cls, field_name)
        if not edge.enabled:
            continue
        cands = _resolve_target_cls(model_cls, field_name, models)
        if not cands:
            continue
        fks.append(
            CascadeEdge(
                path=f"{parent_path}.{field_name}",
                target=cands[0].__name__,
                is_collection=True,
                recurse_into_target=True,
                refresh_target_ttl=True,
                refresh_target_special_keys=True,
                resets_depth_budget=edge.override,
                depth=edge.depth,
                candidates=([c.__name__ for c in cands] if len(cands) > 1 else None),
            )
        )


def _static_walk_special_suffixes(model_cls: Any, parent_path: str = "") -> list[str]:
    """Dotted-path special-field suffixes for model_cls, recursing into nested sub-models."""
    # Lazy import breaks the rapyer.base -> rapyer.cascade module cycle.
    from rapyer.base import AtomicRedisModel

    suffixes: list[str] = []
    for field_name, spec in model_cls._field_specs.items():
        if not (
            spec.external is not None
            and spec.external.field_type.traits() & FieldTrait.OWNS_KEYS
        ):
            continue
        field_path = f"{parent_path}.{field_name}"
        suffixes.append(field_path.lstrip("."))
    for field_name, spec in model_cls._field_specs.items():
        if not spec.reaches & FieldTrait.OWNS_KEYS:
            continue
        field_cls = spec.field_type
        # Only nested models have a per-class suffix set; container-of-SF (list[RedisSet]) don't.
        if not safe_issubclass(field_cls, AtomicRedisModel):
            continue
        nested_path = f"{parent_path}.{field_name}"
        suffixes.extend(_static_walk_special_suffixes(field_cls, nested_path))
    return suffixes


def build_cascade_plan(
    models: list[type["AtomicRedisModel"]],
) -> dict[str, CascadePlanEntry]:
    """Build the static, per-class cascade plan table baked into the Lua script."""
    plan: dict[str, CascadePlanEntry] = {}
    for model_cls in models:
        fks: list[CascadeEdge] = []
        _static_walk_fk_edges(model_cls, "$", fks, models)
        plan[model_cls.__name__] = CascadePlanEntry(
            ttl=model_cls.Meta.ttl,
            special_suffixes=_static_walk_special_suffixes(model_cls),
            fks=fks,
        )
    return plan


def validate_cascade_ttl_targets(plan: dict[str, CascadePlanEntry]):
    """Raise CascadeTargetTtlMissingError when a cascade participant lacks a Meta.ttl."""
    for class_name, entry in sorted(plan.items()):
        for edge in entry.fks:
            # A single-target edge carries candidates=None, so this loops once.
            for target in edge.candidates or [edge.target]:
                # A partial plan may omit a target; surface a RapyerError, not a bare KeyError.
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


def validate_cascade_key_initials(models: list[type["AtomicRedisModel"]]):
    """
    Raise CascadeKeyInitialsError when a cascade participant's class_key_initials()
    is not its __name__.
    """
    plan = build_cascade_plan(models)
    participant_names: set[str] = set()
    for class_name, entry in plan.items():
        if entry.fks:
            # A cascade root EXPIREs its own key, so its prefix is load-bearing too.
            participant_names.add(class_name)
        for edge in entry.fks:
            # A single-target edge carries candidates=None, so this loops once.
            for target in edge.candidates or [edge.target]:
                participant_names.add(target)

    models_by_name = {model.__name__: model for model in models}
    for name in sorted(participant_names):
        cls = models_by_name.get(name)
        if cls is None:
            # A missing target is validate_cascade_ttl_targets' concern; skip here.
            continue
        # Traversal matches a reached {class}:{pk} prefix against __name__-keyed candidates.
        initials = cls.class_key_initials()
        if initials != cls.__name__:
            raise CascadeKeyInitialsError(
                cls.__name__,
                f"{cls.__name__!r} participates in the cascade plan but its "
                f"class_key_initials() returns {initials!r}, not its __name__ "
                f"{cls.__name__!r}; cascade class resolution matches the reached "
                "key's {class}:{pk} prefix against __name__-keyed candidates, so "
                "an override would silently mis-resolve or dead-end the cascade",
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
    """Serialize the full cascade plan to compact JSON."""
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
    # Hash in both names avoids server-global Redis Function name clashes across processes.
    plan_hash = cascade_plan_hash(plan_json)
    return (
        f"{CASCADE_LIBRARY_PREFIX}_{plan_hash}",
        f"{CASCADE_FUNCTION_PREFIX}_{plan_hash}",
    )


def cascade_plan_lua_literal(plan_json: str) -> str:
    """Wrap the compact plan JSON in a Lua long-bracket literal so it embeds verbatim."""
    # Plan JSON is identifier/path data only, but guard anyway since this bakes into source.
    if "]==]" in plan_json:
        raise CascadeLuaLiteralError(
            "cascade plan JSON contains the Lua long-bracket delimiter ']==]', "
            "which would break out of the embedded literal"
        )
    return f"[==[{plan_json}]==]"
