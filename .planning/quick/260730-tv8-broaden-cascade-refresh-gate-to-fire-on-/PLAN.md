---
quick_id: 260730-tv8
slug: broaden-cascade-refresh-gate
date: 2026-07-30
status: in-progress
---

# Quick Task: Broaden the cascade-refresh trigger gate

## Objective

Route any model with special-field keys or FK edges (direct or nested) through the
cascade Redis Function on `refresh_ttl`; keep only plain scalar models on the native
`EXPIRE` fast path.

## Change

Rename `AtomicRedisModel._contains_foreign_key` → `_needs_cascade_script` and broaden it:

```python
bool(
    _relational_field_names   # direct FK
    or _contain_fk            # container/nested holding FK (incl. SF-of-FK)
    or _special_field_names   # direct special field (RedisSet/PQ/RedisText/...)
    or _contain_sf            # link to a model that holds a special field
)
```

## Tasks

1. `rapyer/base.py` — rename + broaden the gate; update both fast-path call sites.
2. `tests/action_groups.py` — rename the freeze-test entry.
3. Tests — reverse `test_plain_sf_container_without_fk_stays_off_the_cascade_path`
   (a plain `RedisSet[str]` model now DOES need the script) and fix the docstring
   reference in `test_cascade_sf_only_trigger_gate.py`.

## Verification

- Full unit suite; full real-Redis integration suite (:6370), run in SEPARATE pytest
  invocations (unit fixtures mock `Meta.redis`, which leaks into the integration
  conftest if combined).
- Fix any test that asserted a plain-SF model takes the EXPIRE fast path.

## Tradeoff (accepted by user)

Plain-SF models (very common) move from pipelined `EXPIRE` to an FCALL per refresh —
simpler, uniform "structured model → script" rule, at a per-refresh cost. Watch the
TTL benchmarks (milestone recently fixed a bulk-insert-with-TTL perf regression).
