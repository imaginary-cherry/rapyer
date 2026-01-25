local key = KEYS[1]
local path = ARGV[1]
local operand = tonumber(ARGV[2])

local current_json = redis.call('JSON.GET', key, path)
if not current_json or current_json == 'null' then
    return nil
end

--[[EXTRACT_VALUE]]
local result = value / operand
redis.call('JSON.SET', key, path, result)
return result
