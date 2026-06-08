local SF_SAVE = {}
local SF_LOAD = {}
--[[SF_DISPATCH_TABLE]]

local main_key = KEYS[1]
local path = ARGV[1]
local main_data = ARGV[2]

local existed = redis.call('EXISTS', main_key)
if existed == 1 then
    local current = redis.call('JSON.GET', main_key, path)
    local out = {0, current}
    local i = 3
    while i <= #ARGV do
        local loader = SF_LOAD[ARGV[i]]
        if loader then
            local result = loader(ARGV[i + 1])
            if result ~= nil then
                out[#out + 1] = cjson.encode(result)
            end
        end
        i = i + 3
    end
    return out
end

redis.call('JSON.SET', main_key, path, main_data)
local i = 3
while i <= #ARGV do
    local saver = SF_SAVE[ARGV[i]]
    if saver then
        saver(ARGV[i + 1], ARGV[i + 2])
    end
    i = i + 3
end
return {1, main_data}
