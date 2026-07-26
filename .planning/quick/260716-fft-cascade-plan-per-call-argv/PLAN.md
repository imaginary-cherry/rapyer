---
phase: quick
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - rapyer/cascade/planner.py
  - rapyer/scripts/lua/cascade/apply.lua
  - rapyer/scripts/registry.py
  - rapyer/init.py
  - rapyer/base.py
  - tests/integration/foreign_keys/test_cascade_ttl_apply.py
  - tests/integration/foreign_keys/test_cascade_graph_shapes.py
  - tests/unit/cascade/test_cascade_apply_lua.py
  - tests/unit/cascade/test_cascade_apply_lua_syntax.py
  - tests/unit/cascade/test_aset_ttl_cascade_flag.py
  - tests/unit/cascade/test_refresh_ttl_cascade_branch.py
  - tests/unit/cascade/test_cascade_action_boundary.py
  - tests/unit/cascade/test_cascade_plan_injection.py
  - tests/unit/test_init_rapyer.py
autonomous: true
requirements: [PERF-CASCADE-ARGV]

must_haves:
  truths:
    - "The cascade Lua script no longer bakes any per-class plan into its body at SCRIPT LOAD"
    - "Each root ships only its reachable-plan subset (root + transitively reachable classes) as JSON in ARGV[5]"
    - "Per-call cost is O(reachable classes), not O(all registered models)"
    - "aset_ttl and refresh_ttl still ALWAYS run the cascade script (unified design, no branch flag)"
    - "Existing cascade behavior (dangling counts, graph shapes, depth budgets, noscript recovery, CascadeResult) is unchanged"
  artifacts:
    - path: "rapyer/cascade/planner.py"
      provides: "reachable_plan_subset + cascade_plan_json helpers"
      contains: "def reachable_plan_subset"
    - path: "rapyer/scripts/lua/cascade/apply.lua"
      provides: "cjson.decode(ARGV[5]) plan load, no CASCADE_PLAN_TABLE placeholder"
      contains: "cjson.decode(ARGV[5]"
  key_links:
    - from: "rapyer/init.py"
      to: "model._cascade_plan_arg"
      via: "cascade_plan_json(reachable_plan_subset(plan, model.__name__))"
      pattern: "_cascade_plan_arg"
    - from: "rapyer/base.py refresh_ttl/aset_ttl"
      to: "run_sha ARGV[5]"
      via: "self._cascade_plan_arg appended as final run_sha arg"
      pattern: "self\\._cascade_plan_arg"
---

<objective>
Optimize per-call cascade-TTL cost. Today `rapyer/scripts/lua/cascade/apply.lua` bakes the ENTIRE per-class `CASCADE_PLAN` table (all N registered models) into its body at SCRIPT LOAD via the `--[[CASCADE_PLAN_TABLE]]` placeholder, so every EVALSHA rebuilds the full N-entry Lua table (~50µs/call at 184 models, ~83% of the TTL-path overhead that regressed CodSpeed's `test_benchmark_with_ttl`).

Fix: ship only the root's reachable-plan subset per call as a compact JSON `ARGV[5]`, precomputed and cached on each model at `init_rapyer`. Per-call cost becomes O(reachable classes).

Purpose: eliminate the O(all-registered) Lua-table rebuild on the hot TTL path without changing any observable cascade behavior.
Output: two new planner helpers, a slimmed Lua header that `cjson.decode`s the plan from ARGV[5], deleted baking machinery in the registry, a cached `_cascade_plan_arg` per model, updated call sites, and reworked tests.

Design is DECIDED. Do not re-derive. The Lua reads only `entry.special_suffixes`, `entry.fks`, and (for non-root reached children) `entry.ttl` — the root uses `root_ttl=ARGV[3]` and its own `ttl` is never read, but the root's SPECIAL keys DO need its plan entry (`queue_special_refresh` reads `classes[root].special_suffixes`). So the subset must contain the root class + every transitively edge-reachable target class. Superset-safe: ignore depth budgets when computing the closure; cycle-safe via a visited set.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@rapyer/cascade/planner.py
@rapyer/scripts/lua/cascade/apply.lua
@rapyer/scripts/registry.py
@rapyer/init.py

<interfaces>
Plan dataclasses (rapyer/cascade/planner.py), verified:

CascadePlanEntry(ttl: int | None, special_suffixes: list[str], fks: list[CascadeEdge])
CascadeEdge(path, target, is_collection, recurse_into_target, refresh_target_ttl,
            refresh_target_special_keys, resets_depth_budget, depth: int | None = None)
build_cascade_plan(models) -> dict[str, CascadePlanEntry]   # keyed by class name
validate_cascade_ttl_targets(plan)                          # already guarantees every
                                                            # reachable participant exists + has non-None ttl
edge.target is the target class name (str). All edges today have recurse_into_target=True.

Current ARGV order (apply.lua): [1]=root_class, [2]=special_prefix, [3]=root_ttl,
[4]=do_cascade flag. NEW: [5]=plan JSON.

Lua header to replace (lines 4-8):
  local CASCADE_PLAN = {}
  --[[CASCADE_PLAN_TABLE]]
  -- comment about baking at SCRIPT LOAD
  local classes = CASCADE_PLAN

Verified call sites appending the plan arg as final run_sha arg:
  rapyer/base.py refresh_ttl (~line 254): run_sha(pipe, NAME, 1, self.key, __name__, PREFIX, self.Meta.ttl, 1)
  rapyer/base.py aset_ttl   (~line 603): run_sha(pipe, NAME, 1, self.key, __name__, PREFIX, ttl, 1 if cascade else 0)
  ClassVars block on AtomicRedisModel: rapyer/base.py lines 165-173.

CRITICAL for mock-based test assertions: `_cascade_plan_arg` is a CLASS attribute on
globally-registered models that init_rapyer mutates in place and never resets. Under
full-suite ordering a prior init_rapyer call leaves REAL JSON on the class, so any
`assert_called_*_with` expected tuple MUST read the live value via
`type(model)._cascade_plan_arg` — NEVER hardcode `"{}"`.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add reachable_plan_subset + cascade_plan_json to planner.py</name>
  <files>rapyer/cascade/planner.py</files>
  <action>
Add `import json` to the module-top imports (dataclasses already imported; module-top only).

Add two module-level functions (module-top scope, not nested):

1. `reachable_plan_subset(plan: dict[str, CascadePlanEntry], root_class: str) -> dict[str, CascadePlanEntry]`:
   - BFS/DFS closure over `edge.target` starting at `root_class`.
   - Always include `root_class` in the result if present in `plan`.
   - Skip any target absent from `plan` (do not KeyError).
   - Cycle-safe: track visited class names in a set.
   - Return a dict mapping class name -> CascadePlanEntry (the subset).
   Superset-safe by design: ignore depth budgets when walking edges (follow every edge).

2. `cascade_plan_json(subset: dict[str, CascadePlanEntry]) -> str`:
   - `dataclasses.asdict` each entry, then recursively drop None-valued keys (so `depth=None` and `ttl=None` vanish — mirrors the existing `_lua_literal` None-omission convention).
   - `json.dumps(..., separators=(",", ":"))` for compactness.
   - Return the JSON string.

Follow project comment style: WHY-only short comments; prefer no docstring (names are self-explanatory). No workflow tags.
  </action>
  <verify>
    <automated>python -c "from rapyer.cascade.planner import reachable_plan_subset, cascade_plan_json; print('ok')"</automated>
  </verify>
  <done>Both functions importable; reachable_plan_subset is cycle-safe and skips absent targets; cascade_plan_json omits None depth/ttl and emits compact JSON.</done>
</task>

<task type="auto">
  <name>Task 2: Slim apply.lua to decode the plan from ARGV[5] and fix the syntax test</name>
  <files>rapyer/scripts/lua/cascade/apply.lua, tests/unit/cascade/test_cascade_apply_lua_syntax.py</files>
  <action>
apply.lua: Replace lines 4-8 (the `local CASCADE_PLAN = {}` line, the `--[[CASCADE_PLAN_TABLE]]` placeholder, the baking comment, and `local classes = CASCADE_PLAN`) with:

  -- The reachable-plan subset for THIS root is shipped per call as JSON in
  -- ARGV[5] (root + its transitively reachable classes, precomputed at
  -- init_rapyer), decoded once here -- replacing the SCRIPT-LOAD-time bake of
  -- every registered model's plan. `or '{}'` degrades a missing arg to a
  -- root-own-keys-only refresh.
  local CASCADE_PLAN = cjson.decode(ARGV[5] or '{}')
  local classes = CASCADE_PLAN

Leave everything downstream untouched: it still indexes `classes[name]`; `cjson.decode` of JSON `{}` yields an empty table that `queue_special_refresh`/`fk_edges` nil-entry guards and `ipairs`/`#edges==0` already handle. ARGV[1..4] semantics unchanged.

test_cascade_apply_lua_syntax.py (BLOCKER fix): line 12 currently asserts
`assert "--[[CASCADE_PLAN_TABLE]]" in text` — this WILL fail after the placeholder is
removed. Invert it: assert the placeholder is ABSENT (`"--[[CASCADE_PLAN_TABLE]]" not in text`)
AND that `"cjson.decode(ARGV[5]" in text`. Keep the existing `script_load(text)` compile
check and the `isinstance(sha, str)` / truthy-sha assertions untouched. Preserve the AAA
section markers.
  </action>
  <verify>
    <automated>grep -c "cjson.decode(ARGV\[5\]" rapyer/scripts/lua/cascade/apply.lua; test $(grep -c "CASCADE_PLAN_TABLE" rapyer/scripts/lua/cascade/apply.lua) -eq 0 && echo "placeholder-removed"; REDIS_DB=0 python -m pytest tests/unit/cascade/test_cascade_apply_lua_syntax.py -q -p no:randomly</automated>
  </verify>
  <done>apply.lua contains `cjson.decode(ARGV[5] or '{}')`; the `--[[CASCADE_PLAN_TABLE]]` placeholder is gone from both the script and the syntax test; the syntax test asserts placeholder-absent + decode-present and still compiles the script.</done>
</task>

<task type="auto">
  <name>Task 3: Remove cascade-plan baking from registry.py</name>
  <files>rapyer/scripts/registry.py</files>
  <action>
Delete the cascade-plan baking entirely:
- Delete `_inject_cascade_plan` (lines ~127-143).
- Delete `_lua_literal` (lines ~90-124).
- Delete the `CASCADE_PLAN_PLACEHOLDER` constant (line ~51).
- Delete `from dataclasses import asdict` (line 1) — no longer used.
- Delete the TYPE_CHECKING `from rapyer.cascade.planner import CascadePlanEntry` import (line 28).

In `build_script_texts`:
- Drop the `cascade_plan = build_cascade_plan(REDIS_MODELS)` line.
- Drop the `from rapyer.cascade.planner import build_cascade_plan` late import (no longer used).
- Drop the second loop that calls `_inject_cascade_plan`.
- Keep the SF-dispatch injection loop (`_inject_sf_dispatch`) untouched.
- Update the surrounding comment so it no longer mentions cascade-plan injection.

`register_scripts`, `run_sha`, `arun_sha`, `handle_noscript_error`, `SCRIPT_REGISTRY`, `SF_DISPATCH_PLACEHOLDER` all unchanged. Confirm no dangling references to removed symbols remain. No new in-function imports (keep the existing SpecialFieldType/REDIS_MODELS late imports).
  </action>
  <verify>
    <automated>python -c "src=open('rapyer/scripts/registry.py').read(); assert not any(s in src for s in ['CASCADE_PLAN_PLACEHOLDER','_inject_cascade_plan','_lua_literal','build_cascade_plan','asdict']), 'residual baking refs'; import rapyer.scripts.registry; print('ok')"</automated>
  </verify>
  <done>No references to CASCADE_PLAN_PLACEHOLDER, _inject_cascade_plan, _lua_literal, build_cascade_plan, or asdict remain; module imports cleanly; SF-dispatch injection intact.</done>
</task>

<task type="auto">
  <name>Task 4: Add _cascade_plan_arg ClassVar and append it as ARGV[5] in base.py</name>
  <files>rapyer/base.py</files>
  <action>
Add `_cascade_plan_arg: ClassVar[str] = "{}"` to the class-level ClassVars on `AtomicRedisModel` (near lines 165-173, alongside `_special_field_names`/`_relational_field_names`/`_contain_fk`). Default `"{}"` so a model used before `init_rapyer` degrades to a root-own-keys-only refresh rather than raising. Plain model ClassVar, NOT a Meta field.

In `refresh_ttl` (~line 254): append `self._cascade_plan_arg` as the FINAL positional arg to `run_sha` (after the `1` cascade flag → ARGV[5]). Add ONE short WHY comment here (only occurrence needing a comment): reachable-plan subset shipped per call instead of baked into the script.

In `aset_ttl` (~line 603): append `self._cascade_plan_arg` as the FINAL positional arg to `run_sha` (after `1 if cascade else 0` → ARGV[5]). No new comment needed.

Do NOT reintroduce any `_has_cascade`-style branch flag. Both methods still ALWAYS run the script (unified design). CascadeResult API unchanged. EVALSHA/Redis 6.0 compat preserved. Comment style: WHY-only, short, no workflow tags, no docstring purely for docs.
  </action>
  <verify>
    <automated>python -c "from rapyer.base import AtomicRedisModel; assert AtomicRedisModel._cascade_plan_arg == '{}'; print('ok')"; test $(grep -c "self\._cascade_plan_arg" rapyer/base.py) -eq 2 && echo "two-call-sites"</automated>
  </verify>
  <done>AtomicRedisModel._cascade_plan_arg defaults to "{}"; both refresh_ttl and aset_ttl append self._cascade_plan_arg as the final run_sha arg; no branch flag introduced.</done>
</task>

<task type="auto">
  <name>Task 5: Cache per-model reachable-subset JSON in init_rapyer</name>
  <files>rapyer/init.py</files>
  <action>
Add `cascade_plan_json, reachable_plan_subset` to the existing module-top import `from rapyer.cascade.planner import build_cascade_plan, validate_cascade_ttl_targets` (module-top only, keep alphabetical).

Replace the current line ~79 `validate_cascade_ttl_targets(build_cascade_plan(REDIS_MODELS))` with:

    plan = build_cascade_plan(REDIS_MODELS)
    validate_cascade_ttl_targets(plan)
    for model in REDIS_MODELS:
        model._cascade_plan_arg = cascade_plan_json(
            reachable_plan_subset(plan, model.__name__)
        )

Keep this INSIDE the existing `try` block (before the `finally` refreeze). `_cascade_plan_arg` is a plain model ClassVar, not a Meta field, so the Meta freeze is irrelevant to setting it here.
  </action>
  <verify>
    <automated>python -c "import ast; ast.parse(open('rapyer/init.py').read()); src=open('rapyer/init.py').read(); assert 'reachable_plan_subset' in src and 'cascade_plan_json' in src and 'model._cascade_plan_arg' in src; print('ok')"</automated>
  </verify>
  <done>init_rapyer builds the plan once, validates it, and caches each model's _cascade_plan_arg inside the existing try block; helpers imported at module top.</done>
</task>

<task type="auto">
  <name>Task 6: Update script-invocation call sites in tests to pass ARGV[5]</name>
  <files>tests/integration/foreign_keys/test_cascade_ttl_apply.py, tests/integration/foreign_keys/test_cascade_graph_shapes.py, tests/unit/cascade/test_cascade_apply_lua.py, tests/unit/cascade/test_aset_ttl_cascade_flag.py, tests/unit/cascade/test_refresh_ttl_cascade_branch.py, tests/unit/cascade/test_cascade_action_boundary.py</files>
  <action>
Integration `_apply_cascade(real_redis_client, root)` helpers in `test_cascade_ttl_apply.py` (line ~20) and `test_cascade_graph_shapes.py` (line ~18) currently call `arun_sha(..., root.key, type(root).__name__, prefix, ttl)` — confirm exact current tail; add the explicit cascade flag `1` (if missing) AND the plan JSON as ARGV[5]: `..., type(root).Meta.ttl, 1, type(root)._cascade_plan_arg`. Each test must still assert the same behavior.

`tests/unit/cascade/test_cascade_apply_lua.py`: the `_apply_cascade(fake_redis_client, root, cascade=True)` helper (lines ~36-47) already passes the cascade flag; append `type(root)._cascade_plan_arg` as the final `arun_sha` arg (ARGV[5]).

`tests/unit/cascade/test_aset_ttl_cascade_flag.py` and `tests/unit/cascade/test_refresh_ttl_cascade_branch.py`: these mock `rapyer.base.scripts_registry.run_sha` and assert exact args via `assert_called_once_with(...)`. base.py now appends `self._cascade_plan_arg`. Add the trailing expected arg to each `assert_called_once_with` block, and it MUST be `type(model)._cascade_plan_arg` read from the live model class — do NOT hardcode `"{}"`. Reason: `_cascade_plan_arg` is a class attribute on globally-registered models that init_rapyer mutates and never resets, so under full-suite ordering a prior init_rapyer leaves real JSON on the class; a literal `"{}"` would mismatch intermittently. Use the class-attr form unconditionally.

`tests/unit/cascade/test_cascade_action_boundary.py`: asserts `run_sha` called once and `call_args.args[1] == CASCADE_TTL_APPLY_SCRIPT_NAME`. Appending a trailing ARGV does not change `args[1]` — confirm it still passes. If it (or any sibling assertion) pins the full arg tuple via `assert_called_*_with`, the trailing ARGV[5] value there MUST also be `type(model)._cascade_plan_arg`, never a literal.

Read each file's exact call site before editing. Follow AAA section markers where present.
  </action>
  <verify>
    <automated>REDIS_DB=0 python -m pytest tests/unit/cascade/test_aset_ttl_cascade_flag.py tests/unit/cascade/test_refresh_ttl_cascade_branch.py tests/unit/cascade/test_cascade_action_boundary.py tests/unit/cascade/test_cascade_apply_lua.py tests/integration/foreign_keys/test_cascade_ttl_apply.py tests/integration/foreign_keys/test_cascade_graph_shapes.py -q -p no:randomly</automated>
  </verify>
  <done>All six touched test files pass with the trailing plan-JSON arg wired through; every mock expected-tuple reads the value via `type(model)._cascade_plan_arg`, no hardcoded `"{}"`.</done>
</task>

<task type="auto">
  <name>Task 7: Replace test_cascade_plan_injection.py with tests for the new mechanism</name>
  <files>tests/unit/cascade/test_cascade_plan_injection.py</files>
  <action>
This file tests the REMOVED `_inject_cascade_plan`/`_lua_literal`/`CASCADE_PLAN_PLACEHOLDER` Lua-literal injection + quote escaping. Replace its contents (may also rename to `test_cascade_plan_subset.py` if that reads clearer — keep the filename if unsure) with tests for the NEW helpers:

(a) `reachable_plan_subset` closure correctness:
    - cycle-safe (A→B→A returns {A,B}, no infinite loop);
    - diamond graph (A→B, A→C, B→D, C→D returns {A,B,C,D});
    - excludes unreachable classes (a class in the full plan not reachable from root is absent from the subset);
    - root-only for a no-edge model (returns just the root entry);
    - includes transitively-reached targets;
    - skips a target absent from the plan without raising.

(b) `cascade_plan_json`:
    - omits None `depth` and None `ttl` keys;
    - round-trips via `json.loads` to the expected dict shape (class name -> {special_suffixes, fks[, ttl]}).

Keep any still-valid trivial `SCRIPT_REGISTRY`/constant assertions. Build fixtures from `CascadePlanEntry`/`CascadeEdge` directly (no Redis needed). Use AAA section markers. No workflow tags in comments.
  </action>
  <verify>
    <automated>python -c "src=open('tests/unit/cascade/test_cascade_plan_injection.py').read(); assert '_inject_cascade_plan' not in src and 'CASCADE_PLAN_PLACEHOLDER' not in src and 'reachable_plan_subset' in src; print('ok')" 2>/dev/null || python -c "import glob; f=glob.glob('tests/unit/cascade/test_cascade_plan_*.py'); src=''.join(open(x).read() for x in f); assert '_inject_cascade_plan' not in src and 'reachable_plan_subset' in src; print('ok')"</automated>
  </verify>
  <done>The removed-injection tests are gone; new tests cover reachable_plan_subset (cycle/diamond/unreachable/root-only/transitive/absent-target) and cascade_plan_json (None omission + json round-trip).</done>
</task>

<task type="auto">
  <name>Task 8: Fix test_init_rapyer.py injection assertions, drop dead imports, add _cascade_plan_arg coverage</name>
  <files>tests/unit/test_init_rapyer.py</files>
  <action>
Around lines 14-16: remove imports of `CASCADE_PLAN_PLACEHOLDER` and `_inject_cascade_plan` (now deleted from registry).

Around lines 8-9: ALSO remove the `REDIS_MODELS` and `build_cascade_plan` imports — they are used ONLY at line 270 (the `_inject_cascade_plan(raw_template, build_cascade_plan(REDIS_MODELS))` expected value), which is deleted below. Leaving them triggers ruff F401 and fails Task 9's `ruff check`. If either symbol turns out to still be used elsewhere in the file, keep only the genuinely-used one — confirm by grepping the file after editing.

Lines ~224, ~263, ~270: the test asserting "every placeholder-bearing template gets injected" must now assert ONLY SF-dispatch injection (cascade plan is no longer injected into script text). Drop the `CASCADE_PLAN_PLACEHOLDER` branch and the `_inject_cascade_plan(raw_template, build_cascade_plan(REDIS_MODELS))` expected value; keep the SF-dispatch equivalence check.

Add a focused test/assertion: after `init_rapyer`, each model's `_cascade_plan_arg` is populated — valid JSON (`json.loads` succeeds) and, for a cascade root, the decoded subset contains at least its own class name. Also add the O(reachable) proof: a NO-edge model's `_cascade_plan_arg` decodes to at most its own class (its own entry, so its special_suffixes are available) and NOT the full registry — assert `set(json.loads(model._cascade_plan_arg)) <= {model.__name__}` for a no-edge model, proving O(reachable) not O(all registered).

Read the file to find the exact fixtures/model names in use. AAA markers where present.
  </action>
  <verify>
    <automated>python -c "src=open('tests/unit/test_init_rapyer.py').read(); assert 'CASCADE_PLAN_PLACEHOLDER' not in src and '_inject_cascade_plan' not in src; print('ok')"; ruff check tests/unit/test_init_rapyer.py; REDIS_DB=0 python -m pytest tests/unit/test_init_rapyer.py -q -p no:randomly</automated>
  </verify>
  <done>test_init_rapyer.py no longer references removed injection symbols; REDIS_MODELS/build_cascade_plan dead imports dropped (ruff clean); asserts SF-dispatch-only injection; verifies each model gets valid-JSON _cascade_plan_arg and a no-edge model's subset is O(reachable) not the full registry.</done>
</task>

<task type="auto">
  <name>Task 9: Add real-Redis subtree-refresh regression + confirm full suite green</name>
  <files>tests/integration/foreign_keys/test_cascade_ttl_apply.py</files>
  <action>
Add (or confirm) at least one explicit integration assertion that a cascade root whose subset flows through `_cascade_plan_arg`/ARGV[5] refreshes the WHOLE reachable subtree exactly as before: build a root with a reachable child (and a special-field key if the fixture models support it), set no TTL on the children directly, run the updated `_apply_cascade(real_redis_client, root)` (which now passes the per-call plan), and assert every reachable key's TTL was set to its owning class's Meta.ttl (children) / root_ttl (root). The updated helper already exercises the new path — ensure the assertion explicitly proves the subtree was refreshed via the per-call plan, not a baked plan.

Then run the full formatting/lint/test verification (see <verification>). Fix any black/ruff findings on touched files.
  </action>
  <verify>
    <automated>black --check rapyer/ tests/ && ruff check rapyer/ tests/ && REDIS_DB=0 python -m pytest tests -q -p no:randomly</automated>
  </verify>
  <done>New/confirmed integration assertion proves per-call-plan subtree refresh; black + ruff clean on all touched files; full suite green (0 failures), including pre-existing dangling / graph-shape / depth-budget / noscript-recovery Lua tests.</done>
</task>

</tasks>

<verification>
- `black --check rapyer/ tests/` clean on all touched files.
- `ruff check rapyer/ tests/` clean (import ordering / unused imports — note the dead REDIS_MODELS/build_cascade_plan imports dropped in Task 8).
- Full suite green against real Redis Stack: `REDIS_DB=0 python -m pytest tests -q -p no:randomly` (localhost; project runs Redis Stack on :6370). 0 failures.
- Specifically confirm the pre-existing dangling / graph-shape / depth-budget / noscript-recovery Lua tests still pass — the `cjson.decode` path must not change any happy-path or dangling behavior.
- Grep confirms `--[[CASCADE_PLAN_TABLE]]`, `_inject_cascade_plan`, `_lua_literal`, `CASCADE_PLAN_PLACEHOLDER` are fully removed from `rapyer/` AND from `tests/` (including the syntax test).
</verification>

<success_criteria>
- apply.lua decodes the plan from ARGV[5]; no plan is baked at SCRIPT LOAD.
- Each model carries a cached `_cascade_plan_arg` (reachable subset JSON) after init_rapyer; default `"{}"` before.
- refresh_ttl and aset_ttl both append `_cascade_plan_arg` as ARGV[5] and still always run the script.
- Per-call plan is O(reachable), proven by a no-edge model's subset containing only its own class.
- No behavior change: dangling counts, graph shapes, depth budgets, noscript recovery, CascadeResult all unchanged.
- black + ruff clean; full real-Redis suite green.
</success_criteria>

<output>
Single logical commit:
`perf(cascade): ship reachable plan subset per call via ARGV instead of baking the full plan into the script (PR #283 review)`
with trailer `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
</output>
