from rapyer.errors import ScriptsNotInitializedError

REMOVE_RANGE_SCRIPT_NAME = "remove_range"
NUM_MUL_SCRIPT_NAME = "num_mul"
NUM_FLOORDIV_SCRIPT_NAME = "num_floordiv"
NUM_MOD_SCRIPT_NAME = "num_mod"
NUM_POW_SCRIPT_NAME = "num_pow"
NUM_TRUEDIV_SCRIPT_NAME = "num_truediv"
STR_APPEND_SCRIPT_NAME = "str_append"

_REMOVE_RANGE_SCRIPT_TEMPLATE = """
local key = KEYS[1]
local path = ARGV[1]
local start_idx = tonumber(ARGV[2])
local end_idx = tonumber(ARGV[3])

local arr_json = redis.call('JSON.GET', key, path)
if not arr_json or arr_json == 'null' then
    return nil
end

{extract_array}
local n = #arr

if start_idx < 0 then start_idx = n + start_idx end
if end_idx < 0 then end_idx = n + end_idx end
if start_idx < 0 then start_idx = 0 end
if end_idx < 0 then end_idx = 0 end
if end_idx > n then end_idx = n end
if start_idx >= n or start_idx >= end_idx then return true end

local new_arr = {{}}
local j = 1

for i = 1, start_idx do
    new_arr[j] = arr[i]
    j = j + 1
end

for i = end_idx + 1, n do
    new_arr[j] = arr[i]
    j = j + 1
end

local encoded = j == 1 and '[]' or cjson.encode(new_arr)
redis.call('JSON.SET', key, path, encoded)
return true
"""

_EXTRACT_ARRAY_REDIS = "local arr = cjson.decode(arr_json)[1]"
_EXTRACT_ARRAY_FAKEREDIS = "local arr = cjson.decode(arr_json)"

REMOVE_RANGE_SCRIPT = _REMOVE_RANGE_SCRIPT_TEMPLATE.format(
    extract_array=_EXTRACT_ARRAY_REDIS
)
REMOVE_RANGE_SCRIPT_FAKEREDIS = _REMOVE_RANGE_SCRIPT_TEMPLATE.format(
    extract_array=_EXTRACT_ARRAY_FAKEREDIS
)

_NUM_MUL_SCRIPT_TEMPLATE = """
local key = KEYS[1]
local path = ARGV[1]
local operand = tonumber(ARGV[2])

local current_json = redis.call('JSON.GET', key, path)
if not current_json or current_json == 'null' then
    return nil
end

{extract_value}
local result = value * operand
redis.call('JSON.SET', key, path, result)
return result
"""

_NUM_FLOORDIV_SCRIPT_TEMPLATE = """
local key = KEYS[1]
local path = ARGV[1]
local operand = tonumber(ARGV[2])

local current_json = redis.call('JSON.GET', key, path)
if not current_json or current_json == 'null' then
    return nil
end

{extract_value}
local result = math.floor(value / operand)
redis.call('JSON.SET', key, path, result)
return result
"""

_NUM_MOD_SCRIPT_TEMPLATE = """
local key = KEYS[1]
local path = ARGV[1]
local operand = tonumber(ARGV[2])

local current_json = redis.call('JSON.GET', key, path)
if not current_json or current_json == 'null' then
    return nil
end

{extract_value}
local result = value % operand
redis.call('JSON.SET', key, path, result)
return result
"""

_NUM_POW_SCRIPT_TEMPLATE = """
local key = KEYS[1]
local path = ARGV[1]
local operand = tonumber(ARGV[2])

local current_json = redis.call('JSON.GET', key, path)
if not current_json or current_json == 'null' then
    return nil
end

{extract_value}
local result = math.floor(value ^ operand)
redis.call('JSON.SET', key, path, result)
return result
"""

_NUM_TRUEDIV_SCRIPT_TEMPLATE = """
local key = KEYS[1]
local path = ARGV[1]
local operand = tonumber(ARGV[2])

local current_json = redis.call('JSON.GET', key, path)
if not current_json or current_json == 'null' then
    return nil
end

{extract_value}
local result = value / operand
redis.call('JSON.SET', key, path, result)
return result
"""

_STR_APPEND_SCRIPT_TEMPLATE = """
local key = KEYS[1]
local path = ARGV[1]
local suffix = ARGV[2]

local current_json = redis.call('JSON.GET', key, path)
if not current_json or current_json == 'null' then
    return nil
end

{extract_value}
local result = value .. suffix
redis.call('JSON.SET', key, path, cjson.encode(result))
return result
"""

_EXTRACT_VALUE_REDIS = "local value = tonumber(cjson.decode(current_json)[1])"
_EXTRACT_VALUE_FAKEREDIS = "local value = tonumber(cjson.decode(current_json)[1])"
_EXTRACT_STR_REDIS = "local value = cjson.decode(current_json)[1]"
_EXTRACT_STR_FAKEREDIS = "local value = cjson.decode(current_json)[1]"

NUM_MUL_SCRIPT = _NUM_MUL_SCRIPT_TEMPLATE.format(extract_value=_EXTRACT_VALUE_REDIS)
NUM_MUL_SCRIPT_FAKEREDIS = _NUM_MUL_SCRIPT_TEMPLATE.format(extract_value=_EXTRACT_VALUE_FAKEREDIS)
NUM_FLOORDIV_SCRIPT = _NUM_FLOORDIV_SCRIPT_TEMPLATE.format(extract_value=_EXTRACT_VALUE_REDIS)
NUM_FLOORDIV_SCRIPT_FAKEREDIS = _NUM_FLOORDIV_SCRIPT_TEMPLATE.format(extract_value=_EXTRACT_VALUE_FAKEREDIS)
NUM_MOD_SCRIPT = _NUM_MOD_SCRIPT_TEMPLATE.format(extract_value=_EXTRACT_VALUE_REDIS)
NUM_MOD_SCRIPT_FAKEREDIS = _NUM_MOD_SCRIPT_TEMPLATE.format(extract_value=_EXTRACT_VALUE_FAKEREDIS)
NUM_POW_SCRIPT = _NUM_POW_SCRIPT_TEMPLATE.format(extract_value=_EXTRACT_VALUE_REDIS)
NUM_POW_SCRIPT_FAKEREDIS = _NUM_POW_SCRIPT_TEMPLATE.format(extract_value=_EXTRACT_VALUE_FAKEREDIS)
NUM_TRUEDIV_SCRIPT = _NUM_TRUEDIV_SCRIPT_TEMPLATE.format(extract_value=_EXTRACT_VALUE_REDIS)
NUM_TRUEDIV_SCRIPT_FAKEREDIS = _NUM_TRUEDIV_SCRIPT_TEMPLATE.format(extract_value=_EXTRACT_VALUE_FAKEREDIS)
STR_APPEND_SCRIPT = _STR_APPEND_SCRIPT_TEMPLATE.format(extract_value=_EXTRACT_STR_REDIS)
STR_APPEND_SCRIPT_FAKEREDIS = _STR_APPEND_SCRIPT_TEMPLATE.format(extract_value=_EXTRACT_STR_FAKEREDIS)

SCRIPTS: dict[str, str] = {
    REMOVE_RANGE_SCRIPT_NAME: REMOVE_RANGE_SCRIPT,
    NUM_MUL_SCRIPT_NAME: NUM_MUL_SCRIPT,
    NUM_FLOORDIV_SCRIPT_NAME: NUM_FLOORDIV_SCRIPT,
    NUM_MOD_SCRIPT_NAME: NUM_MOD_SCRIPT,
    NUM_POW_SCRIPT_NAME: NUM_POW_SCRIPT,
    NUM_TRUEDIV_SCRIPT_NAME: NUM_TRUEDIV_SCRIPT,
    STR_APPEND_SCRIPT_NAME: STR_APPEND_SCRIPT,
}

SCRIPTS_FAKEREDIS: dict[str, str] = {
    REMOVE_RANGE_SCRIPT_NAME: REMOVE_RANGE_SCRIPT_FAKEREDIS,
    NUM_MUL_SCRIPT_NAME: NUM_MUL_SCRIPT_FAKEREDIS,
    NUM_FLOORDIV_SCRIPT_NAME: NUM_FLOORDIV_SCRIPT_FAKEREDIS,
    NUM_MOD_SCRIPT_NAME: NUM_MOD_SCRIPT_FAKEREDIS,
    NUM_POW_SCRIPT_NAME: NUM_POW_SCRIPT_FAKEREDIS,
    NUM_TRUEDIV_SCRIPT_NAME: NUM_TRUEDIV_SCRIPT_FAKEREDIS,
    STR_APPEND_SCRIPT_NAME: STR_APPEND_SCRIPT_FAKEREDIS,
}

_REGISTERED_SCRIPT_SHAS: dict[str, str] = {}


def is_fakeredis(client) -> bool:
    return "fakeredis" in type(client).__module__


async def register_scripts(redis_client):
    scripts = SCRIPTS_FAKEREDIS if is_fakeredis(redis_client) else SCRIPTS
    for name, script_text in scripts.items():
        sha = await redis_client.script_load(script_text)
        _REGISTERED_SCRIPT_SHAS[name] = sha


def run_sha(pipeline, script_name: str, keys: int, *args):
    sha = _REGISTERED_SCRIPT_SHAS.get(script_name)
    if sha is None:
        raise ScriptsNotInitializedError(
            f"Script '{script_name}' not loaded. Did you forget to call init_rapyer()?"
        )
    pipeline.evalsha(sha, keys, *args)


async def handle_noscript_error(redis_client):
    await register_scripts(redis_client)
