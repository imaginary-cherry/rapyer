local key = KEYS[1]
local path = ARGV[1]
local suffix = ARGV[2]

local current_json = redis.call('JSON.GET', key, path)
if not current_json or current_json == 'null' then
    return nil
end

--[[EXTRACT_STR]]
local result = value .. suffix
redis.call('JSON.SET', key, path, cjson.encode(result))
return result
