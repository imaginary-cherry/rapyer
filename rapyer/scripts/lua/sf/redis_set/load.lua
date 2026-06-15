function(special_key)
    return redis.call('SMEMBERS', special_key)
end
