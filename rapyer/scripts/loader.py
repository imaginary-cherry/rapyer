"""Assembles the cascade Redis Functions library from the plan and the Lua template."""

from rapyer.cascade.planner import cascade_names, cascade_plan_lua_literal
from rapyer.scripts.templates import load_template

CASCADE_LIB_TOKEN = "RAPYER_CASCADE_LIB"
CASCADE_FN_TOKEN = "RAPYER_CASCADE_FN"
CASCADE_PLAN_LITERAL_TOKEN = "RAPYER_CASCADE_PLAN_LITERAL"


def build_cascade_library(plan_json: str) -> tuple[str, str, str]:
    """Return (library_name, function_name, source) for the cascade Redis Functions library."""
    library_name, function_name = cascade_names(plan_json)
    # No VARIANTS/SF-dispatch pass: cascade has no SF placeholder and never loads on fakeredis.
    source = load_template("cascade", "library")
    source = source.replace(CASCADE_LIB_TOKEN, library_name)
    source = source.replace(CASCADE_FN_TOKEN, function_name)
    source = source.replace(
        CASCADE_PLAN_LITERAL_TOKEN, cascade_plan_lua_literal(plan_json)
    )
    return library_name, function_name, source
