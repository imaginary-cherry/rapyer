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
        -- (type, key, argc, arg1..argN): loaders need only the key, but the
        -- walk still has to step over this field's args to reach the next one.
        local argc = tonumber(ARGV[i + 2])
        local loader = SF_LOAD[ARGV[i]]
        if loader then
            local result = loader(ARGV[i + 1])
            if result ~= nil then
                out[#out + 1] = cjson.encode(result)
            end
        end
        i = i + 3 + argc
    end
    return out
end

-- Apply special-field savers before writing the main document. Redis Lua does
-- not roll back on error, so persisting main_key last keeps the existence
-- sentinel unset on saver failure, letting a retry re-run cleanly instead of
-- leaving a committed main doc with only partial special-field state.
local i = 3
while i <= #ARGV do
    local argc = tonumber(ARGV[i + 2])
    local saver = SF_SAVE[ARGV[i]]
    if saver then
        -- Hand over a base offset rather than a copied table: ARGV is already a
        -- table, so savers unpack straight off it and pay nothing per argument.
        saver(ARGV[i + 1], i + 3, argc)
    end
    i = i + 3 + argc
end
redis.call('JSON.SET', main_key, path, main_data)
return {1, main_data}
