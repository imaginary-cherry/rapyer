local main_key = KEYS[1]
local path = ARGV[1]
local main_data = ARGV[2]
local save_cmds = cjson.decode(ARGV[3])
local load_cmds = cjson.decode(ARGV[4])

local existed = redis.call('EXISTS', main_key)
if existed == 1 then
    local current = redis.call('JSON.GET', main_key, path)
    local out = {0, current}
    for _, cmd in ipairs(load_cmds) do
        out[#out + 1] = cjson.encode(redis.call(unpack(cmd)))
    end
    return out
end

redis.call('JSON.SET', main_key, path, main_data)
for _, cmd in ipairs(save_cmds) do
    redis.call(unpack(cmd))
end
return {1, main_data}
