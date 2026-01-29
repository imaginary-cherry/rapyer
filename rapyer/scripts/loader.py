from functools import lru_cache
from importlib import resources


VARIANTS = {
    "redis": {
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
    "fakeredis": {
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


@lru_cache(maxsize=None)
def _load_template(category: str, name: str) -> str:
    package = f"rapyer.scripts.lua.{category}"
    filename = f"{name}.lua"
    return resources.files(package).joinpath(filename).read_text()


def load_script(category: str, name: str, variant: str = "redis") -> str:
    template = _load_template(category, name)
    replacements = VARIANTS[variant]
    result = template
    for placeholder, value in replacements.items():
        result = result.replace(f"--[[{placeholder}]]", value)
    return result
