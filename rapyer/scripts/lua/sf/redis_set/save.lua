function(special_key, payload)
    redis.call('DEL', special_key)
    if payload and payload ~= '' then
        local members = cjson.decode(payload)
        for i = 1, #members, 4000 do
            redis.call('SADD', special_key, unpack(members, i, math.min(i + 3999, #members)))
        end
    end
end
