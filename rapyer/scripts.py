REMOVE_RANGE_SCRIPT_NAME = "remove_range"
REMOVE_RANGE_SCRIPT = """
local key = KEYS[1]
local path = ARGV[1]
local start_idx = tonumber(ARGV[2])
local end_idx = tonumber(ARGV[3])

local arr_json = redis.call('JSON.GET', key, path)
if not arr_json or arr_json == 'null' then
    return nil
end

local result = cjson.decode(arr_json)
local arr = result[1]
local n = #arr

if start_idx < 0 then start_idx = n + start_idx end
if end_idx < 0 then end_idx = n + end_idx end
if start_idx < 0 then start_idx = 0 end
if end_idx > n then end_idx = n end
if start_idx >= n or start_idx >= end_idx then return true end

local new_arr = {}
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
SCRIPTS: dict[str, str] = {
    REMOVE_RANGE_SCRIPT_NAME: REMOVE_RANGE_SCRIPT,
}

_REGISTERED_SCRIPT_SHAS: dict[str, str] = {}


async def register_scripts(redis_client):
    for name, script_text in SCRIPTS.items():
        sha = await redis_client.script_load(script_text)
        _REGISTERED_SCRIPT_SHAS[name] = sha


def get_script_sha(name: str) -> str:
    return _REGISTERED_SCRIPT_SHAS.get(name)
