---
quick_id: 260730-tv8
slug: broaden-cascade-refresh-gate
date: 2026-07-30
status: complete
---

# Summary: Broaden the cascade-refresh trigger gate

## What changed

`AtomicRedisModel._contains_foreign_key` → **`_needs_cascade_script`**, broadened to:

```python
bool(_relational_field_names or _contain_fk or _special_field_names or _contain_sf)
```

Now **any** model with an FK edge (direct or containing) **or** a special field (direct
or nested via a link) uses the cascade Redis Function on `refresh_ttl`/`aset_ttl`. Only
plain scalar models keep the native-`EXPIRE` fast path. Both fast-path call sites in
`base.py` updated.

## Files

- `rapyer/base.py` — rename + broaden gate; both call sites.
- `tests/action_groups.py` — freeze-test entry renamed.
- `tests/unit/cascade/test_cascade_sf_held_ref_plan.py` — reversed the plain-SF test:
  a `RedisSet[str]`/`RedisPriorityQueue[float]` model is not an FK edge source but now
  `_needs_cascade_script() is True`.
- `tests/unit/cascade/test_cascade_sf_only_trigger_gate.py` — docstring reference updated.

## Verification

- Full unit: **820 passed** (no fallout — no unit test assumed a plain-SF fast path).
- Full integration (real Redis :6370): **1623 passed / 205 skipped**, zero regression.
  Ran unit and integration in separate pytest invocations.

## Notes

- Correct because the cascade script refreshes the same keys the old EXPIRE fast path did
  (root JSON + special-field keys via the plan's `special_suffixes`), following no edge
  when there are none.
- **Tradeoff (accepted):** plain-SF models (common) now issue an FCALL per refresh instead
  of pipelined EXPIRE. Integration wall-time rose ~76s→~97s across runs — may be this
  overhead or real-Redis noise. Recommend a look at the TTL/bulk benchmarks before merge,
  given the milestone recently fixed a bulk-insert-with-TTL perf regression.
- Method name is no longer FK-specific, hence the rename to `_needs_cascade_script`.
