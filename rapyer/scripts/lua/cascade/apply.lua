-- An unbounded recursion budget: keep following edges with no depth cap.
local UNBOUNDED = -1

local CASCADE_PLAN = {}
--[[CASCADE_PLAN_TABLE]]
-- The per-class cascade data (special-key suffixes + FK edges) is baked into the
-- script at SCRIPT LOAD via the placeholder above; the body indexes it by class.
local classes = CASCADE_PLAN

local root_key = KEYS[1]
local root_class = ARGV[1]
-- The bare special-key prefix (no separators). This script owns the ':'
-- separators and assembles the full key as prefix .. ':' .. key .. ':' ..
-- suffix; it is the Lua-side counterpart of special_field_key on the Python
-- side. The prefix value and the per-class suffixes are shipped as data.
local special_prefix = ARGV[2]
-- The root's own explicit ttl: applies ONLY to the root's own keys (main +
-- special), never to any cascade-reached child -- every child still expires at
-- its owning class's baked-in Meta.ttl.
local root_ttl = tonumber(ARGV[3])

-- Collect-phase state: the read walk queues every key needing a refresh (deduped
-- into refresh_order); the shell at the bottom holds the one mutation (the EXPIRE
-- loop) so the write window stays as small as possible. Every queued entry
-- carries its OWNING CLASS alongside the key so the write phase can look up
-- that class's own Meta.ttl -- no single caller-supplied ttl is ever used, and
-- no GT/NX/XX flag is ever passed to EXPIRE.
-- `visited` is a best-budget-per-node map, not a boolean set: for
-- each key it holds the LARGEST budget any path has offered it so far, so a
-- shared node reached via two paths carrying different finite depth budgets
-- is walked (and its descendants reached) at the larger of the two, regardless
-- of which DFS stack frame happens to pop first.
local visited = {}
local pending_refresh = {}
local refresh_order = {}
local stack = {}

local function queue_refresh(full_key, class_name, is_root, is_special)
    is_root = is_root or false
    is_special = is_special or false
    if not pending_refresh[full_key] then
        pending_refresh[full_key] = true
        refresh_order[#refresh_order + 1] = {
            key = full_key,
            class = class_name,
            is_root = is_root,
            is_special = is_special,
        }
    end
end

local function queue_special_refresh(key, class_name, is_root)
    local entry = classes[class_name]
    if not entry then
        return
    end
    for _, suffix in ipairs(entry.special_suffixes) do
        queue_refresh(special_prefix .. ':' .. key .. ':' .. suffix, class_name, is_root, true)
    end
end

local function fk_edges(class_name)
    local entry = classes[class_name]
    if entry then
        return entry.fks
    end
    return {}
end

-- Read every reference path of a node in ONE JSON.GET and return a
-- path -> target-value map. JSON.GET's output shape depends on arg count
-- (verified identical on real redis and fakeredis):
--   * one path  -> a bare array of matches, e.g. ["A:1"] (or [] when missing)
--   * many paths -> an object keyed by the path string, each value such an
--     array, e.g. {"$.a":["A:1"],"$.b":[]} (order not guaranteed -> key by path)
-- Either way a match is the first array element. A live reference is either a
-- single target-key string (shape 1) or a table of target-key strings/objects
-- (shape 2, collection-of-FK); push_edges below does the type-specific
-- filtering per edge.collection -- this function only strips absent/null
-- matches so both shapes reach push_edges intact.
local function read_reference_paths(key, paths)
    -- unpack is the Lua 5.1 global redis runs on; spreads the paths as args.
    local raw = redis.call('JSON.GET', key, unpack(paths))
    local values_by_path = {}
    if not raw or raw == '' then
        return values_by_path
    end
    local decoded = cjson.decode(raw)
    if #paths == 1 then  -- single-path JSON.GET returns a bare array, not an object
        local match = decoded[1]
        if match ~= nil and match ~= cjson.null then
            values_by_path[paths[1]] = match
        end
        return values_by_path
    end
    for _, path in ipairs(paths) do
        local matches = decoded[path]
        local match = matches and matches[1]
        if match ~= nil and match ~= cjson.null then
            values_by_path[path] = match
        end
    end
    return values_by_path
end

-- Runtime per-edge follow/budget decision: the Python-side classifier only does
-- static, single-hop classification; ALL multi-hop budget bookkeeping happens
-- here. For one edge out of a node whose subtree budget is `remaining_budget`
-- (UNBOUNDED = no cap) and whose subtree is already `established`, decide whether
-- to follow the edge and what budget the child carries. Returns
-- (follow, child_budget).
--
-- An explicit per-field override (edge.override) always wins and REFRESHES the
-- child's budget to this edge's own depth, ignoring any inherited
-- remaining_budget -- this is how a deeper explicit field extends past a
-- shallower ancestor. A blanket edge instead sets the budget on the first hop of
-- a fresh subtree (not yet established) and decrements it on every subsequent
-- established hop; the visited-set stays the real termination backstop, this is
-- only the optional cap.
--
-- edge.depth is absent on an unbounded edge, so edge_depth stays UNBOUNDED. A
-- depth=0 edge therefore yields a child budget of 0 (reach the target, follow no
-- further BLANKET hops) -- never -1, so it can never alias the UNBOUNDED
-- sentinel. The `remaining_budget <= 0` stop below is only ever reached for a
-- real (non-UNBOUNDED) budget, because UNBOUNDED is caught first.
local function next_hop(edge, remaining_budget, established)
    local edge_depth = UNBOUNDED
    if type(edge.depth) == 'number' then
        edge_depth = edge.depth
    end
    if edge.override then
        return true, edge_depth
    end
    if not established then
        return true, edge_depth
    end
    if remaining_budget == UNBOUNDED then
        return true, UNBOUNDED
    end
    if remaining_budget <= 0 then
        return false, 0
    end
    return true, remaining_budget - 1
end

-- Nil-safe, UNBOUNDED-safe budget comparison: nil (never offered before)
-- counts as smaller than any real budget; UNBOUNDED counts as the largest
-- possible value; two UNBOUNDED values are equal, not "larger."
local function budget_is_larger(new_budget, old_budget)
    if old_budget == nil then
        return true
    end
    if new_budget == UNBOUNDED then
        return old_budget ~= UNBOUNDED
    end
    if old_budget == UNBOUNDED then
        return false
    end
    return new_budget > old_budget
end

local function push_child(target_key, edge, budget)
    if type(target_key) == 'string' and budget_is_larger(budget, visited[target_key]) then
        -- Record the new best budget at PUSH time (not pop time) so a later,
        -- even-larger push for the same key is still correctly detected
        -- against the latest recorded best, and a smaller push arriving
        -- afterward is correctly rejected.
        visited[target_key] = budget
        stack[#stack + 1] = {
            key = target_key,
            -- The edge already carries its target's class name, so the
            -- child's class is read straight from the plan, never parsed
            -- back out of the key.
            class = edge.target,
            edge = edge,
            budget = budget,
            -- A child's subtree is always established: it was entered via a
            -- cascade edge. Only the root frame is not-yet-established.
            established = true,
        }
    end
end

-- Worklist of (key, class, budget, established) frames: budget is the number of
-- remaining BLANKET hops still allowed out of `key` (UNBOUNDED = no cap), and
-- established marks whether `key`'s subtree was already entered via cascade. The
-- per-edge follow/budget decision lives entirely in next_hop; a node whose own
-- budget is 0 can still follow its explicit-override edges (which refresh),
-- matching the field-over-global override precedence _classify_edge bakes
-- into the plan.
local function push_edges(parent_key, parent_class, remaining_budget, established)
    local edges = fk_edges(parent_class)
    if #edges == 0 then
        return  -- no reference paths to read for this class
    end
    local paths = {}
    for _, edge in ipairs(edges) do
        paths[#paths + 1] = edge.path
    end
    -- One JSON.GET reads every edge path of this node, not one per edge.
    local values_by_path = read_reference_paths(parent_key, paths)
    for _, edge in ipairs(edges) do
        local matched = values_by_path[edge.path]
        if matched ~= nil then
            local follow, budget = next_hop(edge, remaining_budget, established)
            if follow then
                if not edge.recurse then
                    -- Not-yet-exercised seam: every edge the planner currently
                    -- emits has recurse=true, so this branch is dead today. A
                    -- non-recursing edge reaches (and refreshes) its target and
                    -- yields it zero traversal budget; the target's own OVERRIDE
                    -- edges can still be followed, since next_hop ignores budget
                    -- for overrides.
                    budget = 0
                end
                if not edge.collection then
                    -- Scalar FK: the matched
                    -- value is a single scalar FK -- the target's key string.
                    if type(matched) == 'string' then
                        push_child(matched, edge, budget)
                    end
                elseif edge.collection then
                    -- Shape 2: list[Reference[T]]/dict[K, Reference[T]] -- the
                    -- matched value is a JSON array (1-indexed Lua sequence) or
                    -- a JSON object (string-keyed Lua table); either way `pairs`
                    -- iterates every element regardless of key shape, and every
                    -- element shares this SAME edge (and therefore budget).
                    if type(matched) == 'table' then
                        for _, target_key in pairs(matched) do
                            push_child(target_key, edge, budget)
                        end
                    end
                end
            end
        end
    end
end

-- The read walk: the root is always fully refreshed (main key + every special
-- key), matching aset_ttl. Cascade edges then control whether each *target*
-- refreshes its main key / special keys and whether traversal continues from it.
-- Returns the ordered, deduped {key=, class=} entries to refresh and mutates no
-- Redis state.
local function plan_refresh_keys()
    queue_refresh(root_key, root_class, true)
    queue_special_refresh(root_key, root_class, true)
    -- The root already got the maximal, unbounded first-hop treatment, so no
    -- cycle back to the root can ever be judged "strictly larger."
    visited[root_key] = UNBOUNDED
    -- The root frame is UNBOUNDED + not-yet-established: the very first hop
    -- out of any cascade root is always treated as entering a fresh subtree.
    push_edges(root_key, root_class, UNBOUNDED, false)

    while #stack > 0 do
        local item = table.remove(stack)
        local key = item.key
        -- Only re-walk this frame if it still represents the current best-
        -- known budget for `key` -- push_child already owns writing
        -- visited[key], so a popped frame whose budget no longer equals the
        -- recorded best is stale (already superseded by a strictly larger
        -- push) and is skipped as a no-op.
        if item.budget == visited[key] then
            local edge = item.edge
            if edge.ttl then
                queue_refresh(key, item.class)
            end
            if edge.special then
                queue_special_refresh(key, item.class)
            end
            push_edges(key, item.class, item.budget, item.established)
        end
    end

    return refresh_order
end

-- Write phase: the only place EXPIRE appears -- issue every queued refresh now
-- that the read walk is complete. The root's own keys (main + special) honor
-- the caller-supplied root_ttl; every other key still expires at its OWNING
-- CLASS's own baked-in Meta.ttl -- a plain relative EXPIRE, never GT/NX/XX
-- flags. A dangling (missing) reached child's key makes EXPIRE a cheap no-op
-- (returns 0); tally those misses (main vs special) so the caller can observe a
-- graph that has drifted out of sync -- the root's own keys are never counted,
-- even if somehow absent.
local dangling_children_count = 0
local dangling_special_count = 0
for _, item in ipairs(plan_refresh_keys()) do
    local ttl = item.is_root and root_ttl or classes[item.class].ttl
    local expired = redis.call('EXPIRE', item.key, ttl)
    if expired == 0 and not item.is_root then
        if item.is_special then
            dangling_special_count = dangling_special_count + 1
        else
            dangling_children_count = dangling_children_count + 1
        end
    end
end

return {dangling_children_count, dangling_special_count}
