import pytest

from rapyer.cascade.planner import CascadeEdge, CascadePlanEntry
from rapyer.scripts.constants import CASCADE_TTL_APPLY_SCRIPT_NAME
from rapyer.scripts.registry import (
    _REGISTERED_SCRIPT_SHAS,
    SCRIPT_REGISTRY,
    _inject_cascade_plan,
    register_scripts,
)


def test_cascade_ttl_apply_script_name_is_registered_constant():
    assert CASCADE_TTL_APPLY_SCRIPT_NAME == "cascade_ttl_apply"


def test_cascade_registry_entry_present():
    assert ("cascade", "apply", CASCADE_TTL_APPLY_SCRIPT_NAME) in SCRIPT_REGISTRY


def test_inject_cascade_plan_is_noop_when_placeholder_absent():
    template = "no placeholder here"
    plan = {"A": CascadePlanEntry(ttl=None, special_suffixes=[], fks=[])}

    assert _inject_cascade_plan(template, plan) == template


@pytest.mark.asyncio
async def test_inject_cascade_plan_escapes_single_quote_in_class_name(
    fake_redis_client,
):
    plan = {"A's": CascadePlanEntry(ttl=5, special_suffixes=[], fks=[])}

    injected = _inject_cascade_plan("--[[CASCADE_PLAN_TABLE]]", plan)

    assert "--[[CASCADE_PLAN_TABLE]]" not in injected
    # A naive, unescaped f-string embed would prematurely close the Lua
    # string literal on the single quote inside "A's" -- wrap the injected
    # assignment lines in a real script and prove it still compiles.
    script = f'local CASCADE_PLAN = {{}}\n{injected}\nreturn CASCADE_PLAN["A\'s"].ttl'
    sha = await fake_redis_client.script_load(script)

    assert isinstance(sha, str)
    assert sha


def test_inject_cascade_plan_serializes_bool_int_and_omits_absent_depth():
    plan = {
        "Foo": CascadePlanEntry(
            ttl=10,
            special_suffixes=["tasks"],
            fks=[
                CascadeEdge(
                    path="$.author",
                    target="Author",
                    collection=False,
                    recurse=True,
                    ttl=True,
                    special=True,
                    override=False,
                )
            ],
        )
    }

    injected = _inject_cascade_plan("--[[CASCADE_PLAN_TABLE]]", plan)

    assert "CASCADE_PLAN['Foo']" in injected
    assert "true" in injected
    assert "false" in injected
    assert "depth" not in injected


@pytest.mark.asyncio
async def test_register_scripts_registers_cascade_ttl_apply(fake_redis_client):
    await register_scripts(fake_redis_client, is_fakeredis=True)

    assert CASCADE_TTL_APPLY_SCRIPT_NAME in _REGISTERED_SCRIPT_SHAS


@pytest.mark.asyncio
async def test_register_scripts_leaves_sf_only_scripts_unaffected(fake_redis_client):
    from rapyer.scripts.constants import ATOMIC_GET_OR_CREATE_SCRIPT_NAME

    await register_scripts(fake_redis_client, is_fakeredis=True)

    assert ATOMIC_GET_OR_CREATE_SCRIPT_NAME in _REGISTERED_SCRIPT_SHAS
