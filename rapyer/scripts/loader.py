from functools import lru_cache
from importlib import resources  # nosemgrep  # py>=3.10, 3.7 compat rule N/A

from rapyer.scripts.constants import FAKEREDIS_VARIANT, REDIS_VARIANT

VARIANTS = {
    REDIS_VARIANT: {
        "EXTRACT_ARRAY": "local arr = cjson.decode(arr_json)[1]",
        "EXTRACT_VALUE": "local value = tonumber(cjson.decode(current_json)[1])",
        "EXTRACT_STR": "local value = cjson.decode(current_json)[1]",
        "EXTRACT_DATETIME": "local value = cjson.decode(current_json)[1]",
        "DICT_EXTRACT_VALUE": "local extracted = cjson.decode(value)[1]",
        "DICT_EXTRACT_POPITEM": """local parsed = cjson.decode(value)
if type(parsed) == 'table' then
    for _, v in pairs(parsed) do
        extracted = v
        break
    end
else
    extracted = parsed
end""",
    },
    FAKEREDIS_VARIANT: {
        "EXTRACT_ARRAY": "local arr = cjson.decode(arr_json)",
        "EXTRACT_VALUE": "local value = tonumber(cjson.decode(current_json)[1])",
        "EXTRACT_STR": "local value = cjson.decode(current_json)[1]",
        "EXTRACT_DATETIME": "local value = cjson.decode(current_json)[1]",
        "DICT_EXTRACT_VALUE": "local extracted = cjson.decode(value)[1]",
        "DICT_EXTRACT_POPITEM": """local parsed = cjson.decode(value)
if type(parsed) == 'table' then
    for _, v in pairs(parsed) do
        extracted = v
        break
    end
else
    extracted = parsed
end""",
    },
}
LUA_SCRIPT_LOCATION = "rapyer.scripts.lua"
SF_SAVE_FILENAME = "save.lua"
SF_LOAD_FILENAME = "load.lua"


@lru_cache(maxsize=None)
def _load_template(category: str, name: str) -> str:
    package = f"{LUA_SCRIPT_LOCATION}.{category}"
    filename = f"{name}.lua"
    return resources.files(package).joinpath(filename).read_text()


def load_script(category: str, name: str, variant: str = REDIS_VARIANT) -> str:
    template = _load_template(category, name)
    replacements = VARIANTS[variant]
    result = template
    for placeholder, value in replacements.items():
        result = result.replace(f"--[[{placeholder}]]", value)
    return result


@lru_cache(maxsize=None)
def _read_sf_file(type_dir: str, filename: str) -> str:
    package = f"{LUA_SCRIPT_LOCATION}.sf.{type_dir}"
    return resources.files(package).joinpath(filename).read_text().rstrip("\n")


def load_sf_save_snippet(type_dir: str) -> str:
    return _read_sf_file(type_dir, SF_SAVE_FILENAME)


def load_sf_load_snippet(type_dir: str) -> str:
    return _read_sf_file(type_dir, SF_LOAD_FILENAME)
