import json

import pytest

from rapyer.cascade.planner import (
    CascadeEdge,
    CascadePlanEntry,
    build_cascade_plan,
    cascade_plan_hash,
    cascade_plan_json,
)
from rapyer.scripts.constants import ATOMIC_GET_OR_CREATE_SCRIPT_NAME
from rapyer.scripts.registry import (
    _REGISTERED_SCRIPT_SHAS,
    SCRIPT_REGISTRY,
    register_scripts,
)
from tests.unit.cascade.conftest import CASCADE_PLANNER_MODELS


def _edge(target: str, candidates: list[str] | None = None) -> CascadeEdge:
    return CascadeEdge(
        path=f"$.{target.lower()}",
        target=target,
        is_collection=False,
        recurse_into_target=True,
        refresh_target_ttl=True,
        refresh_target_special_keys=True,
        resets_depth_budget=False,
        candidates=candidates,
    )


def _entry(*targets: str, ttl: int | None = 10, suffixes=None) -> CascadePlanEntry:
    return CascadePlanEntry(
        ttl=ttl,
        special_suffixes=suffixes or [],
        fks=[_edge(t) for t in targets],
    )


def test_cascade_is_not_an_evalsha_script():
    # Cascade moved to a Redis Functions library, out of the EVALSHA registry.
    assert not any(category == "cascade" for category, _, _ in SCRIPT_REGISTRY)


def test_cascade_plan_json_omits_none_depth_and_ttl():
    # Arrange
    # ttl=None on the entry and depth=None on the edge (its default).
    plan = {"A": _entry("B", ttl=None), "B": _entry(ttl=None)}

    # Act
    payload = cascade_plan_json(plan)

    # Assert
    assert '"ttl"' not in payload
    assert '"depth"' not in payload


def test_cascade_plan_json_round_trips_full_plan_to_expected_shape():
    # Arrange
    plan = {"Foo": _entry("Author", ttl=10, suffixes=["tasks"]), "Author": _entry()}

    # Act
    decoded = json.loads(cascade_plan_json(plan))

    # Assert
    assert set(decoded) == {"Foo", "Author"}
    assert decoded["Foo"]["special_suffixes"] == ["tasks"]
    assert decoded["Foo"]["ttl"] == 10
    assert decoded["Foo"]["fks"][0]["target"] == "Author"
    assert decoded["Author"]["fks"] == []


def test_single_target_plan_json_and_hash_are_byte_identical_golden():
    # Arrange -- the Function library and function names embed this hash.
    plan = {"A": _entry("B"), "B": _entry()}

    # Act
    payload = cascade_plan_json(plan)

    # Assert
    expected = (
        '{"A":{"ttl":10,"special_suffixes":[],"fks":[{"path":"$.b",'
        '"target":"B","is_collection":false,"recurse_into_target":true,'
        '"refresh_target_ttl":true,"refresh_target_special_keys":true,'
        '"resets_depth_budget":false}]},"B":{"ttl":10,"special_suffixes":[],'
        '"fks":[]}}'
    )
    assert payload == expected
    assert cascade_plan_hash(payload) == "0bc1f0e973ecfcf4"
    # candidates=None is dropped: a single-target edge carries no candidates key.
    assert '"candidates"' not in payload


def test_cascade_plan_json_serializes_every_class_in_the_plan():
    # Arrange
    plan = {
        "A": _entry("B"),
        "B": _entry("C"),
        "C": _entry(),
        "Unrelated": _entry(),
    }

    # Act
    decoded = json.loads(cascade_plan_json(plan))

    # Assert
    # The full plan carries every class, including ones not reachable from A.
    assert set(decoded) == {"A", "B", "C", "Unrelated"}


def test_cascade_plan_json_covers_every_built_class(setup_fake_redis_for_cascade_apply):
    # Arrange
    plan = build_cascade_plan(CASCADE_PLANNER_MODELS)

    # Act
    decoded = json.loads(cascade_plan_json(plan))

    # Assert
    for model in CASCADE_PLANNER_MODELS:
        assert model.__name__ in decoded


@pytest.mark.asyncio
async def test_register_scripts_leaves_sf_only_scripts_unaffected(fake_redis_client):
    # Act
    await register_scripts(fake_redis_client, is_fakeredis=True)

    # Assert
    assert ATOMIC_GET_OR_CREATE_SCRIPT_NAME in _REGISTERED_SCRIPT_SHAS
