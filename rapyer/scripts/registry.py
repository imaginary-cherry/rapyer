from typing import TYPE_CHECKING

from redis.exceptions import NoScriptError, ResponseError

from rapyer.cascade.planner import build_cascade_plan, cascade_plan_json
from rapyer.errors import (
    PersistentCascadeFunctionError,
    PersistentNoScriptError,
    ScriptsNotInitializedError,
)
from rapyer.scripts.constants import (
    ATOMIC_GET_OR_CREATE_SCRIPT_NAME,
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
from rapyer.scripts.loader import build_cascade_library, load_script

if TYPE_CHECKING:
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
]

_REGISTERED_SCRIPT_SHAS: dict[str, str] = {}

SF_DISPATCH_PLACEHOLDER = "--[[SF_DISPATCH_TABLE]]"


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


def build_script_texts(is_fakeredis: bool = False) -> dict[str, str]:
    # Late import: SpecialFieldType lives under rapyer.types, which depends on
    # this module via the SCRIPT_REGISTRY constants. Importing at call time
    # avoids the circular import while still letting __subclasses__() see every
    # type that was loaded before init_rapyer() ran.
    from rapyer.types.special import SpecialFieldType

    variant = FAKEREDIS_VARIANT if is_fakeredis else REDIS_VARIANT
    scripts = _build_scripts(variant)
    # Any script in the registry may opt into SF dispatch injection by including
    # the placeholder; templates without it pass through unchanged.
    for name, script_text in scripts.items():
        scripts[name] = _inject_sf_dispatch(script_text, SpecialFieldType)
    return scripts


async def register_scripts(redis_client, is_fakeredis: bool = False) -> None:
    scripts = build_script_texts(is_fakeredis=is_fakeredis)
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


async def register_cascade_function(redis_client, plan_json: str) -> str:
    _library_name, function_name, source = build_cascade_library(plan_json)
    # REPLACE makes re-init idempotent for the same plan and refreshes a changed one.
    await redis_client.function_load(source, replace=True)
    return function_name


def run_fcall(pipeline, function_name: str, keys: int, *args):
    # Enqueue only; self-heal happens at execute time (aexecute_pipeline_with_cascade_self_heal).
    pipeline.fcall(function_name, keys, *args)


async def aretry_fcall_after_missing_function(
    redis_config: "RedisConfig", commands_backup: list
):
    """
    Reload the cascade function, then replay only the backed-up FCALL commands.
    """
    await handle_missing_function(redis_config.redis, redis_config)
    # Re-read the name: handle_missing_function may rewrite it if the plan hash changed.
    async with redis_config.redis.pipeline(transaction=True) as retry_pipe:
        for args, options in commands_backup:
            if args[0] == "FCALL":
                # Rewrite only the function-name slot (args[1]); keep numkeys/keys/args verbatim.
                retry_pipe.execute_command(
                    args[0],
                    redis_config.cascade_function_name,
                    *args[2:],
                    **options,
                )
        try:
            return await retry_pipe.execute()
        except ResponseError as e:
            raise PersistentCascadeFunctionError(
                "Cascade function still missing after re-loading. "
                "This indicates a server-side problem with Redis."
            ) from e


async def aexecute_pipeline_with_cascade_self_heal(pipe, redis_config: "RedisConfig"):
    """
    Execute a pipeline, transparently reloading the cascade function and
    replaying the FCALL on a function-not-found error.
    """
    commands_backup = list(pipe.command_stack)
    try:
        return await pipe.execute()
    except ResponseError as e:
        if "function not found" not in str(e).lower():
            raise
        return await aretry_fcall_after_missing_function(redis_config, commands_backup)


async def handle_missing_function(redis_client, redis_config: "RedisConfig"):
    if redis_config.is_fake_redis:
        return
    # Inline import solely to break the base -> scripts -> base cycle.
    from rapyer.base import REDIS_MODELS

    plan = build_cascade_plan(REDIS_MODELS)
    name = await register_cascade_function(redis_client, cascade_plan_json(plan))
    redis_config.cascade_function_name = name
