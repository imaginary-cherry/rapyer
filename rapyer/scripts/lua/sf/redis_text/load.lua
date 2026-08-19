function(special_key) return redis.call('HGET', special_key, 'text') end
