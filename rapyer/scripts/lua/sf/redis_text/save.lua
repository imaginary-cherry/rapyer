function(special_key, base, argc)
    -- Args arrive as a flat HSET field/value list. ARGV is binary-safe, so the
    -- FLOAT32 embedding ships raw -- no base64, no cjson.
    redis.call('HSET', special_key, unpack(ARGV, base, base + argc - 1))
end
