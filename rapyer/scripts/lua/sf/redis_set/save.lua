function(special_key, base, argc)
    redis.call('DEL', special_key)
    -- Chunked: unpack hits a C-stack limit around 8000 elements.
    for offset = 0, argc - 1, 4000 do
        local last = math.min(offset + 3999, argc - 1)
        redis.call('SADD', special_key, unpack(ARGV, base + offset, base + last))
    end
end
