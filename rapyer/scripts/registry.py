from rapyer.errors import PersistentNoScriptError, ScriptsNotInitializedError
from rapyer.scripts.constants import (
    DATETIME_ADD_SCRIPT_NAME,
    DICT_POP_SCRIPT_NAME,
    DICT_POPITEM_SCRIPT_NAME,
    NUM_FLOORDIV_SCRIPT_NAME,
    NUM_MOD_SCRIPT_NAME,
    NUM_MUL_SCRIPT_NAME,
    NUM_POW_FLOAT_SCRIPT_NAME,
    NUM_POW_SCRIPT_NAME,
    NUM_TRUEDIV_SCRIPT_NAME,
    REMOVE_RANGE_SCRIPT_NAME,
    STR_APPEND_SCRIPT_NAME,
    STR_MUL_SCRIPT_NAME,
)
from rapyer.scripts.loader import load_script
from redis.exceptions import NoScriptError

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
]

_REGISTERED_SCRIPT_SHAS: dict[str, str] = {}


def _build_scripts(variant: str) -> dict[str, str]:
    return {
        name: load_script(category, script, variant)
        for category, script, name in SCRIPT_REGISTRY
    }


def get_scripts() -> dict[str, str]:
    return _build_scripts("redis")


def get_scripts_fakeredis() -> dict[str, str]:
    return _build_scripts("fakeredis")


async def register_scripts(redis_client, is_fakeredis: bool = False) -> None:
    variant = "fakeredis" if is_fakeredis else "redis"
    scripts = _build_scripts(variant)
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


async def arun_sha(client, script_name: str, keys: int, *args):
    sha = get_script(script_name)
    try:
        return await client.evalsha(sha, keys, *args)
    except NoScriptError:
        pass

    await handle_noscript_error(client)
    sha = get_script(script_name)
    try:
        return await client.evalsha(sha, keys, *args)
    except NoScriptError as e:
        raise PersistentNoScriptError(
            "NOSCRIPT error persisted after re-registering scripts. "
            "This indicates a server-side problem with Redis."
        ) from e


async def handle_noscript_error(redis_client):
    await register_scripts(redis_client)
