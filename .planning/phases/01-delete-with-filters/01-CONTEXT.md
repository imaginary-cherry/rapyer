# Phase 1: Delete with Filters - Context

**Gathered:** 2026-02-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Extend `adelete_many` to support filter expressions (`Expression`) and key-based deletion, matching `afind`'s interface flexibility. Currently `adelete_many` only accepts model instances or key strings. This phase adds expression-based filtering and improves the return value. No new CRUD operations — this enhances existing delete functionality.

</domain>

<decisions>
## Implementation Decisions

### Argument handling
- Accept three types of args: model instances (`Self`), key strings (`str`), and filter expressions (`Expression`)
- Keys and model instances can be mixed freely (both are "specific targets" — extract `.key` from models, combine with keys)
- Expressions CANNOT mix with keys/models — raise `TypeError` if both provided
- No arguments raises an error (too dangerous to allow implicit "delete everything")
- Keys get auto-prefixed like `afind`: if no `:` in key, prepend `class_key_initials():`

### Return value
- Return a result model (not plain int) containing `count` (number of actually deleted keys)
- Only `count` field for now, but model allows future extension

### Safety guardrails
- No bulk delete limit — trust the caller
- No-args raises error (decided above)
- Use pipeline for batch deletes (all matching keys deleted in one pipeline)
- Always use direct Redis client — do NOT respect `_context_var` pipeline context

### Query strategy for expressions
- Use cursor-based approach (`FT.AGGREGATE` with `WITHCURSOR` / `FT.CURSOR READ`) for expression queries
- This safely handles arbitrarily large result sets, unlike `FT.SEARCH` which has offset limits around 10k

### Edge cases
- Expression matches zero keys: return result with count=0, no error
- Specific keys that don't exist in Redis: silent skip, count reflects actually deleted
- Stale model instances (key already deleted): silent skip, same as missing key

### Claude's Discretion
- Exact cursor batch size for FT.AGGREGATE pagination
- Result model name and location
- Whether to reuse afind's Expression handling logic or duplicate it

</decisions>

<specifics>
## Specific Ideas

- "See how I implemented something similar in afind" — the `afind` method at `rapyer/base.py:428` is the reference implementation for key/expression separation pattern
- afind uses `Query(query_string).no_content()` for expression-based search — delete should use similar approach but with cursor-based pagination
- The existing `adelete_many` signature uses `*args: Unpack[Self | str]` — needs to expand to include `Expression`

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-delete-with-filters*
*Context gathered: 2026-02-08*
