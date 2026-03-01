local key = KEYS[1]
local path = ARGV[1]
local target_key = ARGV[2]

local value = redis.call('JSON.GET', key, path .. '.' .. target_key)

if value and value ~= '[]' and value ~= 'null' then
    redis.call('JSON.DEL', key, path .. '.' .. target_key)
    --[[DICT_EXTRACT_VALUE]]
    return extracted
else
    return nil
end
