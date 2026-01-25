local key = KEYS[1]
local path = ARGV[1]
local start_idx = tonumber(ARGV[2])
local end_idx = tonumber(ARGV[3])

local arr_json = redis.call('JSON.GET', key, path)
if not arr_json or arr_json == 'null' then
    return nil
end

--[[EXTRACT_ARRAY]]
local n = #arr

if start_idx < 0 then start_idx = n + start_idx end
if end_idx < 0 then end_idx = n + end_idx end
if start_idx < 0 then start_idx = 0 end
if end_idx < 0 then end_idx = 0 end
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
