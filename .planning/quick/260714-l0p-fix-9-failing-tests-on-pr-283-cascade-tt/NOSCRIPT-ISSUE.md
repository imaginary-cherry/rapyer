# Extend NOSCRIPT self-heal to the TTL-refresh pipeline paths (ensure_pipeline / pipeline_with_execution)

**Urgency: High**

After the TTL-cascade feature (PR #283), `refresh_ttl` and `aset_ttl` always run the
cascade `EVALSHA` through `ensure_pipeline` / `pipeline_with_execution`
(`rapyer/context.py`). Both of these now do a bare `await pipe.execute()` with
**no NOSCRIPT self-heal**.

A `SCRIPT FLUSH` (deliberate, or implicit on a fresh/failed-over replica) will
make every TTL refresh through these paths fail with `NoScriptError` and no
retry — there is no re-registration and no replay. This affects:

- The auto TTL-refresh wrapper installed by `install_marked_action_methods`
  (every mutating/reading action on a model with `Meta.ttl` set), which calls
  `refresh_ttl()` -> `ensure_pipeline`/`pipeline_with_execution`.
- `aset_ttl`'s standalone-pipeline branch (`rapyer/base.py`), which now issues
  a bare `pipe.execute()` for the cascade-TTL-apply script.

`_apipeline` (the general model-write path in `rapyer/base.py`) already
self-heals: on `NoScriptError` it re-registers scripts via
`scripts_registry.handle_noscript_error` and replays **only** the `EVALSHA`
entries from the failed command stack (never re-running the ride-along
native commands, since Redis does not roll back a MULTI/EXEC transaction
when one command fails at EXEC time).

**Ask:** extend the same EVALSHA-only-replay recovery that `_apipeline` uses
to `ensure_pipeline` and `pipeline_with_execution` in `rapyer/context.py`, so
TTL-refresh paths self-heal from a `SCRIPT FLUSH` the same way general writes
already do.

Reference: PR #283 review comment on `rapyer/context.py` (comment #10), and
the follow-up scoping decision in
`.planning/quick/260714-l0p-fix-9-failing-tests-on-pr-283-cascade-tt/260714-l0p-REVIEW-FIXES-PLAN.md`
(task 3), which deliberately kept the generic-pipeline NOSCRIPT recovery out
of the TTL-cascade feature and tracked this extension as a separate issue.
