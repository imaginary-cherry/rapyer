local key = KEYS[1]
local path = ARGV[1]

local keys = redis.call('JSON.OBJKEYS', key, path)

if not keys or #keys == 0 then
    return nil
end

if type(keys[1]) == 'table' then
    keys = keys[1]
end

if not keys or #keys == 0 then
    return nil
end

local first_key = tostring(keys[1])
local value = redis.call('JSON.GET', key, path .. '.' .. first_key)

if not value then
    return nil
end

redis.call('JSON.DEL', key, path .. '.' .. first_key)

local extracted
--[[DICT_EXTRACT_POPITEM]]
return {first_key, extracted}
