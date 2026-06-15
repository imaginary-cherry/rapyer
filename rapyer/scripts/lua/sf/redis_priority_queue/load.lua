function(special_key)
    -- Queue items are fetched lazily by aitems/apeek/...; matches aget/aload.
    -- Returning nil tells the main script to omit a slot for this field.
    return nil
end
