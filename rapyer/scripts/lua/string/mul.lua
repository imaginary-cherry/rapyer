local key = KEYS[1]
local path = ARGV[1]
local count = tonumber(ARGV[2])

local current_json = redis.call('JSON.GET', key, path)
if not current_json or current_json == 'null' then
    return nil
end

--[[EXTRACT_STR]]
local result = string.rep(value, count)
redis.call('JSON.SET', key, path, cjson.encode(result))
return result
