from dataclasses import asdict
from typing import TYPE_CHECKING

from redis.exceptions import NoScriptError

from rapyer.errors import PersistentNoScriptError, ScriptsNotInitializedError
from rapyer.scripts.constants import (
    ATOMIC_GET_OR_CREATE_SCRIPT_NAME,
    CASCADE_TTL_APPLY_SCRIPT_NAME,
    DATETIME_ADD_SCRIPT_NAME,
    DICT_POP_SCRIPT_NAME,
    DICT_POPITEM_SCRIPT_NAME,
    FAKEREDIS_VARIANT,
    NUM_FLOORDIV_SCRIPT_NAME,
    NUM_MOD_SCRIPT_NAME,
    NUM_MUL_SCRIPT_NAME,
    NUM_POW_FLOAT_SCRIPT_NAME,
    NUM_POW_SCRIPT_NAME,
    NUM_TRUEDIV_SCRIPT_NAME,
    REDIS_VARIANT,
    REMOVE_RANGE_SCRIPT_NAME,
    STR_APPEND_SCRIPT_NAME,
    STR_MUL_SCRIPT_NAME,
)
from rapyer.scripts.loader import load_script

if TYPE_CHECKING:
    from rapyer.cascade.planner import CascadePlanEntry
    from rapyer.config import RedisConfig

SCRIPT_REGISTRY: list[tuple[str, str, str]] = [
    ("list", "remove_range", REMOVE_RANGE_SCRIPT_NAME),
    ("numeric", "mul", NUM_MUL_SCRIPT_NAME),
    ("numeric", "floordiv", NUM_FLOORDIV_SCRIPT_NAME),
    ("numeric", "mod", NUM_MOD_SCRIPT_NAME),
    ("numeric", "pow", NUM_POW_SCRIPT_NAME),
    ("numeric", "pow_float", NUM_POW_FLOAT_SCRIPT_NAME),
    ("numeric", "truediv", NUM_TRUEDIV_SCRIPT_NAME),
    ("string", "append", STR_APPEND_SCRIPT_NAME),
    ("string", "mul", STR_MUL_SCRIPT_NAME),
    ("datetime", "add", DATETIME_ADD_SCRIPT_NAME),
    ("dict", "pop", DICT_POP_SCRIPT_NAME),
    ("dict", "popitem", DICT_POPITEM_SCRIPT_NAME),
    ("atomic", "get_or_create", ATOMIC_GET_OR_CREATE_SCRIPT_NAME),
    ("cascade", "apply", CASCADE_TTL_APPLY_SCRIPT_NAME),
]

_REGISTERED_SCRIPT_SHAS: dict[str, str] = {}

SF_DISPATCH_PLACEHOLDER = "--[[SF_DISPATCH_TABLE]]"
CASCADE_PLAN_PLACEHOLDER = "--[[CASCADE_PLAN_TABLE]]"


def _build_scripts(variant: str) -> dict[str, str]:
    return {
        name: load_script(category, script, variant)
        for category, script, name in SCRIPT_REGISTRY
    }


def get_scripts() -> dict[str, str]:
    return _build_scripts(REDIS_VARIANT)


def get_scripts_fakeredis() -> dict[str, str]:
    return _build_scripts(FAKEREDIS_VARIANT)


def _inject_sf_dispatch(template: str, sf_base) -> str:
    """
    Replace ``--[[SF_DISPATCH_TABLE]]`` in ``template`` with concrete
    ``SF_SAVE`` / ``SF_LOAD`` assignments, one per direct subclass of
    ``SpecialFieldType``. Each SF class contributes a ``lua_save_snippet``
    and ``lua_load_snippet`` (function literals) keyed by ``lua_type_name``.

    The result is the Lua source that gets ``SCRIPT LOAD``-ed once. Per-call
    ``ARGV`` then only carries identifiers + payloads — the snippets live
    inside the cached SHA.
    """
    if SF_DISPATCH_PLACEHOLDER not in template:
        return template
    lines: list[str] = []
    for sf_cls in sf_base.__subclasses__():
        name = sf_cls.lua_type_name()
        lines.append(f"SF_SAVE[{name!r}] = {sf_cls.lua_save_snippet()}")
        lines.append(f"SF_LOAD[{name!r}] = {sf_cls.lua_load_snippet()}")
    return template.replace(SF_DISPATCH_PLACEHOLDER, "\n".join(lines))


def _lua_literal(value) -> str:
    """
    Serialize a Python value (``dict``/``list``/``str``/``bool``/``int``) into
    a Lua table-literal fragment for embedding into a script template at
    ``SCRIPT LOAD`` time. ``dict`` values that are ``None`` are omitted
    entirely (mirrors ``build_cascade_plan``'s depth-absent-when-unbounded
    convention). Strings are single-quoted with ``\\``/``'`` escaped first —
    this is the injection-mitigation boundary; never raw-interpolate an
    unescaped string into Lua source.
    """
    if isinstance(value, dict):
        parts = [
            f"[{_lua_literal(key)}] = {_lua_literal(inner)}"
            for key, inner in value.items()
            if inner is not None
        ]
        return "{" + ", ".join(parts) + "}"
    if isinstance(value, list):
        return "{" + ", ".join(_lua_literal(item) for item in value) + "}"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        # IN-03: also escape newlines/CR so a stray control char in an injected
        # literal (class name, field path, special suffix) yields valid Lua at
        # SCRIPT LOAD rather than a silently broken script body. Backslash first.
        escaped = (
            value.replace("\\", "\\\\")
            .replace("'", "\\'")
            .replace("\n", "\\n")
            .replace("\r", "\\r")
        )
        return f"'{escaped}'"
    raise TypeError(f"Unsupported cascade-plan Lua literal type: {type(value)!r}")


def _inject_cascade_plan(template: str, plan: dict[str, "CascadePlanEntry"]) -> str:
    """
    Replace ``--[[CASCADE_PLAN_TABLE]]`` in ``template`` with one
    ``CASCADE_PLAN['ClassName'] = {...}`` assignment line per class in
    ``plan`` (``build_cascade_plan``'s output shape). Models-only: every
    entry is a ``CascadePlanEntry`` (no plain-dict acceptance path) and is
    always converted via ``dataclasses.asdict`` before ``_lua_literal``
    serializes the resulting nested-dict shape. No-ops when the placeholder
    is absent, mirroring ``_inject_sf_dispatch``.
    """
    if CASCADE_PLAN_PLACEHOLDER not in template:
        return template
    lines = [
        f"CASCADE_PLAN[{_lua_literal(name)}] = {_lua_literal(asdict(entry))}"
        for name, entry in plan.items()
    ]
    return template.replace(CASCADE_PLAN_PLACEHOLDER, "\n".join(lines))


async def register_scripts(redis_client, is_fakeredis: bool = False) -> None:
    # Late imports: SpecialFieldType lives under rapyer.types, and REDIS_MODELS/
    # build_cascade_plan live under rapyer.base/rapyer.cascade, both of which
    # depend on this module via the SCRIPT_REGISTRY constants. Importing at
    # call time avoids the circular import while still letting __subclasses__()/
    # REDIS_MODELS see every type/model that was loaded before init_rapyer() ran.
    from rapyer.base import REDIS_MODELS
    from rapyer.cascade.planner import build_cascade_plan
    from rapyer.types.special import SpecialFieldType

    variant = FAKEREDIS_VARIANT if is_fakeredis else REDIS_VARIANT
    scripts = _build_scripts(variant)
    cascade_plan = build_cascade_plan(REDIS_MODELS)
    # Any script in the registry may opt into SF dispatch / cascade-plan
    # injection by including the respective placeholder; templates without it
    # pass through unchanged (each helper short-circuits).
    for name, script_text in scripts.items():
        scripts[name] = _inject_sf_dispatch(script_text, SpecialFieldType)
    for name, script_text in scripts.items():
        scripts[name] = _inject_cascade_plan(script_text, cascade_plan)
    for name, script_text in scripts.items():
        sha = await redis_client.script_load(script_text)
        _REGISTERED_SCRIPT_SHAS[name] = sha


def get_script(script_name: str):
    sha = _REGISTERED_SCRIPT_SHAS.get(script_name)
    if sha is None:
        raise ScriptsNotInitializedError(
            f"Script '{script_name}' not loaded. Did you forget to call init_rapyer()?"
        )
    return sha


def run_sha(pipeline, script_name: str, keys: int, *args):
    sha = get_script(script_name)
    pipeline.evalsha(sha, keys, *args)


async def arun_sha(
    client, redis_config: "RedisConfig", script_name: str, keys: int, *args
):
    sha = get_script(script_name)
    try:
        return await client.evalsha(sha, keys, *args)
    except NoScriptError:
        pass

    await handle_noscript_error(client, redis_config)
    sha = get_script(script_name)
    try:
        return await client.evalsha(sha, keys, *args)
    except NoScriptError as e:
        raise PersistentNoScriptError(
            "NOSCRIPT error persisted after re-registering scripts. "
            "This indicates a server-side problem with Redis."
        ) from e


async def handle_noscript_error(redis_client, redis_config: "RedisConfig"):
    await register_scripts(redis_client, is_fakeredis=redis_config.is_fake_redis)
