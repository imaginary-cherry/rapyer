local key = KEYS[1]
local path = ARGV[1]
local delta_seconds = tonumber(ARGV[2])

local current_json = redis.call('JSON.GET', key, path)
if not current_json or current_json == 'null' then
    return nil
end

--[[EXTRACT_DATETIME]]
local pattern = "(%d+)-(%d+)-(%d+)T(%d+):(%d+):(%d+)"
local y, m, d, h, mi, s = string.match(value, pattern)
if not y then return nil end

y = tonumber(y)
m = tonumber(m)
d = tonumber(d)
h = tonumber(h)
mi = tonumber(mi)
s = tonumber(s)

s = s + delta_seconds

while s >= 60 do
    s = s - 60
    mi = mi + 1
end
while s < 0 do
    s = s + 60
    mi = mi - 1
end
while mi >= 60 do
    mi = mi - 60
    h = h + 1
end
while mi < 0 do
    mi = mi + 60
    h = h - 1
end
while h >= 24 do
    h = h - 24
    d = d + 1
end
while h < 0 do
    h = h + 24
    d = d - 1
end

local function is_leap_year(year)
    return (year % 4 == 0 and year % 100 ~= 0) or (year % 400 == 0)
end

local function days_in_month(year, month)
    local days = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31}
    if month == 2 and is_leap_year(year) then
        return 29
    end
    return days[month]
end

while d > days_in_month(y, m) do
    d = d - days_in_month(y, m)
    m = m + 1
    if m > 12 then
        m = 1
        y = y + 1
    end
end
while d < 1 do
    m = m - 1
    if m < 1 then
        m = 12
        y = y - 1
    end
    d = d + days_in_month(y, m)
end

local new_date = string.format("%04d-%02d-%02dT%02d:%02d:%02d", y, m, d, h, mi, s)
redis.call('JSON.SET', key, path, cjson.encode(new_date))
return new_date
