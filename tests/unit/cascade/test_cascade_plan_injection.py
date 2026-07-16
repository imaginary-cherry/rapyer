import json

import pytest

from rapyer.cascade.planner import (
    CascadeEdge,
    CascadePlanEntry,
    cascade_plan_json,
    reachable_plan_subset,
)
from rapyer.scripts.constants import (
    ATOMIC_GET_OR_CREATE_SCRIPT_NAME,
    CASCADE_TTL_APPLY_SCRIPT_NAME,
)
from rapyer.scripts.registry import (
    _REGISTERED_SCRIPT_SHAS,
    SCRIPT_REGISTRY,
    register_scripts,
)


def _edge(target: str) -> CascadeEdge:
    return CascadeEdge(
        path=f"$.{target.lower()}",
        target=target,
        is_collection=False,
        recurse_into_target=True,
        refresh_target_ttl=True,
        refresh_target_special_keys=True,
        resets_depth_budget=False,
    )


def _entry(*targets: str, ttl: int | None = 10, suffixes=None) -> CascadePlanEntry:
    return CascadePlanEntry(
        ttl=ttl,
        special_suffixes=suffixes or [],
        fks=[_edge(t) for t in targets],
    )


def test_cascade_ttl_apply_script_name_is_registered_constant():
    # Act
    # Assert
    assert CASCADE_TTL_APPLY_SCRIPT_NAME == "cascade_ttl_apply"


def test_cascade_registry_entry_present():
    # Act
    # Assert
    assert ("cascade", "apply", CASCADE_TTL_APPLY_SCRIPT_NAME) in SCRIPT_REGISTRY


def test_reachable_plan_subset_is_cycle_safe():
    # Arrange
    # A -> B -> A is a cycle; the closure must terminate.
    plan = {"A": _entry("B"), "B": _entry("A")}

    # Act
    subset = reachable_plan_subset(plan, "A")

    # Assert
    assert set(subset) == {"A", "B"}


def test_reachable_plan_subset_covers_diamond():
    # Arrange
    plan = {
        "A": _entry("B", "C"),
        "B": _entry("D"),
        "C": _entry("D"),
        "D": _entry(),
    }

    # Act
    subset = reachable_plan_subset(plan, "A")

    # Assert
    assert set(subset) == {"A", "B", "C", "D"}


def test_reachable_plan_subset_excludes_unreachable_class():
    # Arrange
    # Unrelated is present in the full plan but not reachable from A.
    plan = {"A": _entry("B"), "B": _entry(), "Unrelated": _entry()}

    # Act
    subset = reachable_plan_subset(plan, "A")

    # Assert
    assert set(subset) == {"A", "B"}
    assert "Unrelated" not in subset


def test_reachable_plan_subset_root_only_for_no_edge_model():
    # Arrange
    plan = {"A": _entry(), "B": _entry()}

    # Act
    subset = reachable_plan_subset(plan, "A")

    # Assert
    assert set(subset) == {"A"}


def test_reachable_plan_subset_includes_transitive_targets():
    # Arrange
    plan = {"A": _entry("B"), "B": _entry("C"), "C": _entry()}

    # Act
    subset = reachable_plan_subset(plan, "A")

    # Assert
    assert set(subset) == {"A", "B", "C"}


def test_reachable_plan_subset_skips_absent_target_without_raising():
    # Arrange
    # A references Missing, which has no plan entry.
    plan = {"A": _entry("Missing")}

    # Act
    subset = reachable_plan_subset(plan, "A")

    # Assert
    assert set(subset) == {"A"}


def test_cascade_plan_json_omits_none_depth_and_ttl():
    # Arrange
    # ttl=None on the entry and depth=None on the edge (its default).
    plan = {"A": _entry("B", ttl=None), "B": _entry(ttl=None)}

    # Act
    payload = cascade_plan_json(reachable_plan_subset(plan, "A"))

    # Assert
    assert '"ttl"' not in payload
    assert '"depth"' not in payload


def test_cascade_plan_json_round_trips_to_expected_shape():
    # Arrange
    plan = {"Foo": _entry("Author", ttl=10, suffixes=["tasks"]), "Author": _entry()}

    # Act
    decoded = json.loads(cascade_plan_json(reachable_plan_subset(plan, "Foo")))

    # Assert
    assert set(decoded) == {"Foo", "Author"}
    assert decoded["Foo"]["special_suffixes"] == ["tasks"]
    assert decoded["Foo"]["ttl"] == 10
    assert decoded["Foo"]["fks"][0]["target"] == "Author"
    assert decoded["Author"]["fks"] == []


@pytest.mark.asyncio
async def test_register_scripts_registers_cascade_ttl_apply(fake_redis_client):
    # Act
    await register_scripts(fake_redis_client, is_fakeredis=True)

    # Assert
    assert CASCADE_TTL_APPLY_SCRIPT_NAME in _REGISTERED_SCRIPT_SHAS


@pytest.mark.asyncio
async def test_register_scripts_leaves_sf_only_scripts_unaffected(fake_redis_client):
    # Act
    await register_scripts(fake_redis_client, is_fakeredis=True)

    # Assert
    assert ATOMIC_GET_OR_CREATE_SCRIPT_NAME in _REGISTERED_SCRIPT_SHAS
