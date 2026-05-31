function(special_key, payload)
    redis.call('DEL', special_key)
    if payload and payload ~= '' then
        local members = cjson.decode(payload)
        if #members > 0 then
            redis.call('SADD', special_key, unpack(members))
        end
    end
end
