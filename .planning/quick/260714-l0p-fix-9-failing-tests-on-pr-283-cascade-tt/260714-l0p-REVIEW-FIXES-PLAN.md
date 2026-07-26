---
phase: quick-260714-l0p-review-fixes
plan: 02
type: execute
wave: 1
depends_on: []
autonomous: true
must_haves:
  truths:
    - "Full suite green after EACH task: REDIS_DB=0 python -m pytest tests -q -p no:randomly (real Redis Stack on localhost:6370). black --check and ruff check clean on touched files."
    - "CascadeEdge field renames are synchronized across the dataclass, the Lua plan table it is injected into (dataclasses.asdict keys), apply.lua's readers, and every test that inspects those fields."
    - "The always-True edge flags (recurse/ttl/special families) are KEPT as documented forward-looking per-edge hooks (not removed), with comments explaining they are extensibility seams for future delete/save-cascade."
    - "aset_ttl always routes through the cascade Lua script; a per-invocation cascade flag (not the baked plan) decides whether edges are followed, so cascade=False refreshes only the root's own keys (main + special) and never traverses an edged class."
    - "The generic-pipeline NOSCRIPT self-heal is removed from context.py (reverted to bare execute on ensure_pipeline/pipeline_with_execution); _apipeline keeps develop's self-contained recovery; a GitHub issue captures extending recovery to the TTL-refresh paths."
---

<objective>
Resolve the PR #283 review comments. Grouped so each commit is atomic and full-suite-gated. Decisions already locked with the user: #8 root-cascade flag, #10 extract recovery + issue, #2/#4 keep flags as documented hooks.
</objective>

<task id="1" label="cosmetic + naming + test-quality (low risk)">
**planner.py — CascadeEdge renames + docs (comments #1,#2,#3,#4,#5,#7):**
- `import dataclasses` and use `@dataclasses.dataclass(frozen=True)` (drop `from dataclasses import dataclass`). Registry.py already imports `asdict` from dataclasses — leave registry as-is unless it also uses bare `dataclass`.
- Rename CascadeEdge fields and update ALL readers (planner construction sites, apply.lua, tests that inspect edges):
  - `collection` → `is_collection` (#3)
  - `recurse` → `recurse_into_target` (#2)
  - `ttl` → `refresh_target_ttl`
  - `special` → `refresh_target_special_keys` (#4)
  - `override` → `resets_depth_budget` (#1)
  - keep `path`, `target`, `depth`.
- Add a short class-level comment on CascadeEdge documenting that `recurse_into_target` / `refresh_target_ttl` / `refresh_target_special_keys` are always True today and are forward-looking per-edge hooks for future delete/save-cascade (the Lua keeps a documented dead branch for the non-recursing case); `resets_depth_budget` means an explicit per-field spec resets the child's depth budget to this edge's depth instead of decrementing the inherited one.
- Fix docstrings that start text on the `"""` line so content begins on the next line (#7) — `_static_walk_fk_edges` and any sibling one-liner-start docstrings in planner.py. Keep true one-line docstrings (`"""One class's full entry..."""`) as-is only if already valid; prefer `"""` on its own line for multi-line ones.
- `special_suffixes` (#6): add a one-line comment on CascadePlanEntry.special_suffixes explaining special fields live under separate Redis keys the Lua must EXPIRE alongside the main key. (Also answered on PR.)

**apply.lua:** update `edge.collection` → `edge.is_collection`, `edge.recurse` → `edge.recurse_into_target`, `edge.ttl` → `edge.refresh_target_ttl`, `edge.special` → `edge.refresh_target_special_keys`, `edge.override` → `edge.resets_depth_budget`. No behavior change.

**config.py + init.py + tests (comment #9):** rename PrivateAttr `_frozen` → `_meta_locked` everywhere (config.py __setattr__ + comment, init.py unfreeze/refreeze/teardown, tests/conftest.py reset_meta_freeze, test_init_rapyer.py, test_cascade_ttl_config.py, test_meta_ttl_freeze.py). Keep behavior identical.

**CodeRabbit #14 — planner.py `_static_walk_special_suffixes`:** unwrap the annotation before the subclass check, mirroring `_unwrap_nested_model_cls`:
`stripped = strip_optional(annotation); field_cls = get_origin(stripped) or stripped` then `safe_issubclass(field_cls, AtomicRedisModel)`. (`strip_optional`/`get_origin` already imported.)

**CodeRabbit #15 — tests/integration/foreign_keys/test_cascade_ttl_apply.py:** tighten the TTL assertion(s) that use SCRIPT_FLUSH_ROOT_TTL_SECONDS (120) so they prove the explicit ttl was applied: `assert 0 < await real_redis_client.ttl(parent.key) <= SCRIPT_FLUSH_ROOT_TTL_SECONDS` (persist first if needed), at the two spots CodeRabbit named (~L169 and L158-170).

**Test comment format (#12, #13) — ALL new cascade tests under tests/integration/foreign_keys/ and tests/unit/cascade/:** where an Arrange/Act/Assert section marker is written inline like `# Assert: the explicit...`, split into a bare section header on its own line, a blank line is not required between header and body but the section label must be its own comment line, e.g.:
    # Assert
    # The explicit cascade never resolved to a dangling reference...
Apply consistently across the new tests added by this feature branch. Only touch comment formatting; do not change test logic.

verify: `REDIS_DB=0 python -m pytest tests -q -p no:randomly` → 0 failures; `black --check` + `ruff check` clean.
commit: `refactor(cascade): clearer CascadeEdge/Meta naming, docstrings, and test comments (PR #283 review)`
</task>

<task id="2" label="#8 unify aset_ttl onto the script via a cascade flag">
**apply.lua:** add `local do_cascade = tonumber(ARGV[4]) ~= 0` (new ARGV[4]; treat missing/nil as 1 for backward-compat callers). In `plan_refresh_keys`, only call the initial `push_edges(root_key, root_class, UNBOUNDED, false)` when `do_cascade` is true. The root's own `queue_refresh` + `queue_special_refresh` always run. This makes a non-cascade call refresh exactly the root's main + special keys and follow no edges.

**base.py aset_ttl:** remove the `if not cascade or not self._has_cascade:` plain-EXPIRE branch entirely. Always run the cascade script, passing the cascade flag as the new ARGV: `1` when `cascade` is True, `0` otherwise. Keep the outer-pipeline early-return and the CascadeResult return for the executed path. Since a non-cascade call now returns via the script too, decide the return contract: preserve `Optional[CascadeResult]` — return None for cascade=False (matches old behavior of returning None), return CascadeResult for cascade=True. Non-positive ttl semantics are preserved because the script EXPIREs the root's own keys with the caller ttl.
- `refresh_ttl` (auto path) already always cascades — pass ARGV cascade=1 there (it should keep the whole subtree alive on every action). Update its run_sha call to include the new ARGV=1.
- Update the registry run_sha/arun_sha call sites for CASCADE_TTL_APPLY to pass the extra arg.

**Tests:** update tests/unit/cascade/test_aset_ttl_cascade_flag.py, test_cascade_apply_lua.py, test_refresh_ttl_cascade_branch.py, and any integration cascade test that invokes the script directly (`_apply_cascade` helper builds the ARGV list) to pass the new cascade ARGV. `_has_cascade` may now be unused by aset_ttl — leave the attribute (init.py still sets it) unless clearly dead; do not remove init.py's `_has_cascade` bookkeeping in this task.

verify: `REDIS_DB=0 python -m pytest tests -q -p no:randomly` → 0 failures. Confirm a cascade=False aset_ttl on an FK-edged model refreshes only the root (add/keep a test asserting the child is NOT refreshed under cascade=False).
commit: `feat(cascade): unify aset_ttl onto the cascade script via a per-call cascade flag (PR #283 #8)`
</task>

<task id="3" label="#10 extract generic-pipeline NOSCRIPT recovery">
**context.py:** remove `execute_pipeline_with_noscript_recovery` and its now-unused imports (`logging`, `NoScriptError`, `ResponseError`, `PersistentNoScriptError`, `scripts_registry`, `logger`). Revert `ensure_pipeline` and `pipeline_with_execution` to `await pipe.execute()` (develop's behavior).

**base.py:** `_apipeline` — restore develop's self-contained inline NOSCRIPT recovery (EVALSHA-only replay + PersistentNoScriptError on second failure) so the general model-write path keeps self-healing exactly as develop does. `aset_ttl` cascade path — replace `execute_pipeline_with_noscript_recovery(pipe, self.Meta)` with `await pipe.execute()` (bare). Remove the `from rapyer.context import execute_pipeline_with_noscript_recovery` import.

**Tests:** remove tests/unit/test_context.py's `execute_pipeline_with_noscript_recovery`-specific tests (the helper no longer exists) — keep any other tests in that file. Update test_aset_ttl_cascade_flag.py:141 which patches `rapyer.base.execute_pipeline_with_noscript_recovery` (patch `Pipeline.execute` or the appropriate seam instead). tests/integration/pipeline/test_pipeline_noscript_recovery.py exercises `_apipeline` via model writes and must still pass against the restored inline recovery.

verify: `REDIS_DB=0 python -m pytest tests -q -p no:randomly` → 0 failures.
commit: `refactor(cascade): keep generic-pipeline NOSCRIPT recovery out of the TTL feature (PR #283 #10)`

**Issue text (orchestrator opens it; executor writes the body to `.planning/quick/260714-l0p-*/NOSCRIPT-ISSUE.md`):** title "Extend NOSCRIPT self-heal to the TTL-refresh pipeline paths (ensure_pipeline / pipeline_with_execution)"; body: after the TTL-cascade feature, refresh_ttl and aset_ttl always run the cascade EVALSHA via ensure_pipeline/pipeline_with_execution, which do a bare pipe.execute() with NO NOSCRIPT self-heal — a SCRIPT FLUSH (or fresh replica) makes every TTL refresh fail with NOSCRIPT and no retry. _apipeline (general model writes) already self-heals; extend the same EVALSHA-only-replay recovery to the TTL-refresh paths. High urgency. Reference PR #283 review comment.
</task>
