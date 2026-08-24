-- Verified against real Redis 7.2.6 at :6370 on 2026-08-19: no `base64` global exists in the
-- Lua sandbox (accessing it raises "Script attempted to access nonexistent global variable
-- 'base64'"); `cjson`, by contrast, resolves as a live table. A base64 decoder must be vendored.
function(special_key, payload)
    -- Public-domain base64 decoder (lua-users wiki), vendored since this codebase has no
    -- cross-file Lua require/include mechanism for SF snippet function literals. `gsub` returns
    -- (string, count), so the outer parens on the chained return drop the count. Costs ~5.7ms
    -- per 1536-dim blob, scaling linearly with dim, on Redis's single thread.
    local function base64_decode(data)
        local b = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
        -- Pass 1: strip everything outside the alphabet.
        data = string.gsub(data, '[^' .. b .. '=]', '')
        -- Pass 2: each char -> its 6 bits as '0'/'1' characters.
        return (data:gsub('.', function(x)
            if x == '=' then return '' end
            local r, f = '', (b:find(x) - 1)
            for i = 6, 1, -1 do
                r = r .. (f % 2 ^ i - f % 2 ^ (i - 1) > 0 and '1' or '0')
            end
            return r
        -- Pass 3: regroup into bytes; `#x ~= 8` drops the padding tail.
        end):gsub('%d%d%d?%d?%d?%d?%d?%d?', function(x)
            if #x ~= 8 then return '' end
            local c = 0
            for i = 1, 8 do
                c = c + (x:sub(i, i) == '1' and 2 ^ (8 - i) or 0)
            end
            return string.char(c)
        end))
    end

    -- JSON can't carry the raw FLOAT32 blob, hence base64 on this path only; asave HSETs the
    -- bytes directly.
    local fields = cjson.decode(payload)
    local decoded_bytes = base64_decode(fields.embedding_b64)
    redis.call('HSET', special_key,
        'text', fields.text,
        'embedding', decoded_bytes,
        'parent', fields.parent,
        'field', fields.field,
        'model_label', fields.model_label)
end
