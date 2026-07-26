---
phase: quick-260720-luc
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - rapyer/utils/annotation.py
  - tests/unit/cascade/test_extract_annotation.py
  - rapyer/scripts/registry.py
  - rapyer/scripts/__init__.py
  - rapyer/context.py
  - rapyer/base.py
  - rapyer/config.py
  - tests/integration/foreign_keys/test_cascade_ttl_apply.py
  - tests/integration/foreign_keys/test_cascade_depth_and_gate.py
  - tests/integration/foreign_keys/test_cascade_graph_shapes.py
  - tests/integration/foreign_keys/test_cascade_self_heal.py
autonomous: true
requirements: [ISSUE-284]

must_haves:
  truths:
    - "extract_annotation and its test file no longer exist; no production code references them"
    - "A missing cascade Redis Function is transparently reloaded and the FCALL retried at all four pipeline-execute sites (context.ensure_pipeline, context.pipeline_with_execution, base.aset_ttl, base._apipeline)"
    - "A single shared self-heal helper is reused by all four sites — retry logic is not duplicated"
    - "arun_fcall no longer exists; the 3 integration test helpers call client.fcall directly"
    - "handle_missing_function and PersistentCascadeFunctionError are retained and used by the new self-heal path"
    - "An integration test proves production self-heal: after FUNCTION FLUSH, a refresh_ttl/aset_ttl call reloads the function and still refreshes the reachable subtree"
    - "fakeredis EXPIRE branch is unchanged; existing Meta.ttl/refresh_ttl behavior and single-FCALL atomicity preserved"
  artifacts:
    - path: "rapyer/scripts/registry.py"
      provides: "Shared aexecute_pipeline_with_cascade_self_heal + aretry_fcall_after_missing_function helpers"
      contains: "aretry_fcall_after_missing_function"
    - path: "tests/integration/foreign_keys/test_cascade_self_heal.py"
      provides: "Production self-heal regression test (issue #284)"
      contains: "function_flush"
  key_links:
    - from: "rapyer/context.py"
      to: "rapyer.scripts.registry.aexecute_pipeline_with_cascade_self_heal"
      via: "lazy in-function import (breaks actions<->context<->scripts<->types cycle)"
      pattern: "aexecute_pipeline_with_cascade_self_heal"
    - from: "rapyer/base.py aset_ttl / _apipeline"
      to: "scripts_registry self-heal helpers"
      via: "scripts_registry.<helper>"
      pattern: "scripts_registry\\.(aexecute_pipeline_with_cascade_self_heal|aretry_fcall_after_missing_function)"
---

<objective>
Remove dead cascade code and promote the issue-#284 cascade-function self-heal into every production pipeline-execute path.

Purpose: Today only the direct-client wrapper `arun_fcall` (used solely by integration tests) recovers from a missing cascade Redis Function. The real production TTL-cascade paths (`refresh_ttl`, `aset_ttl`, and any FCALL enqueued into an outer `_apipeline`) execute the FCALL with NO recovery. This plan factors a single shared self-heal helper, wires it into all four bare-execute sites, deletes the now-redundant `arun_fcall`, and adds the proper real-Redis regression test.

Output: A single shared self-heal helper in `rapyer/scripts/registry.py`; four wired execute sites; `arun_fcall`, `extract_annotation`, and their consumers removed; a new self-heal integration test.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@./CLAUDE.md

<worktree_setup>
Fresh worktree .venv lacks the test extra. Run ONCE before pytest:
`uv sync --extra test --group dev`
Real Redis 7+ with RedisJSON (redis-stack) is on localhost:6370 (integration conftest already targets it). :6379 has NO JSON module — do not use it. Run the full fakeredis unit suite AND the cascade integration tests on :6370. black/ruff/mypy must stay clean. The ruff --fix save hook strips unused imports — add each import together with its first use in the same edit.
</worktree_setup>

<interfaces>
<!-- Extracted from codebase. Use directly; no exploration needed. -->

Existing recovery template to MIRROR — direct-client self-heal in registry.py (being deleted):
```
async def arun_fcall(client, redis_config, keys, *args):
    name = redis_config.cascade_function_name
    try:
        return await client.fcall(name, keys, *args)
    except ResponseError as e:
        if "function not found" not in str(e).lower():
            raise
    await handle_missing_function(client, redis_config)
    name = redis_config.cascade_function_name          # re-read: name may change after reload
    try:
        return await client.fcall(name, keys, *args)
    except ResponseError as e:
        raise PersistentCascadeFunctionError(...) from e
```

Retained helpers (KEEP — used by the new self-heal path):
```
async def handle_missing_function(redis_client, redis_config):  # early-returns on fakeredis; FUNCTION LOADs and rewrites redis_config.cascade_function_name
class PersistentCascadeFunctionError(RapyerError)  # rapyer/errors/cascade.py, re-exported from rapyer.errors
```

Existing NOSCRIPT self-heal in base._apipeline (base.py:1390-1428) — the structural template for the FCALL retry:
  commands_backup = list(pipe.command_stack)   # (args, options) tuples; args[0] is the command name
  try: await pipe.execute() except NoScriptError / ResponseError ...
  on retry: rebuild matching commands in a fresh transactional pipeline, re-execute, raise Persistent* if it fails again.

RedisConfig (rapyer/config.py): `redis` = async client (Meta.redis), `is_fake_redis: bool`, `cascade_function_name: str | None` (writable even when frozen).

context.py managers (both own `await pipe.execute()`):
  ensure_pipeline(meta, should_execute=True) -> executes at line 61 only when it CREATED the pipeline
  pipeline_with_execution(meta) -> always executes at line 68

FCALL command shape in a pipeline: run_fcall enqueues ("FCALL", function_name, numkeys, key, ClassName, SPECIAL_FIELD_KEY_PREFIX, ttl, do_cascade). So in a backed-up command tuple, args[0] == "FCALL" and args[1] == function_name.
</interfaces>

<cycle_note>
CRITICAL — `context.py` MUST NOT import `rapyer.scripts.registry` at module top.
Verified during planning: `import rapyer` loads `context.py` via `actions.py` (base -> actions -> context) while `actions` is still mid-init. A module-top `from rapyer.scripts import registry` in context.py triggers the chain
`registry -> cascade.planner -> types.relational -> types.base -> rapyer.actions` (line 12) / `rapyer.context` (line 13),
re-entering the half-built `actions`/`context` modules -> ImportError. (The task brief's "registry.py is safe to import from context.py" is FALSE for module-top imports.)
Resolution: import `scripts_registry` LAZILY inside the two context.py functions. This is the documented-cycle exception to the no-in-function-imports rule (same pattern used at registry.py handle_missing_function and cascade/planner). base.py already imports `scripts_registry` at top, so aset_ttl/_apipeline need no lazy import.
</cycle_note>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Delete dead extract_annotation and its sole test</name>
  <files>rapyer/utils/annotation.py, tests/unit/cascade/test_extract_annotation.py</files>
  <action>
    Confirm no production references remain (planning grep shows the only references are the function definition and the test file): run `grep -rn "extract_annotation" rapyer/` — it MUST return only the definition line. Then remove the `extract_annotation` function (and its docstring) from rapyer/utils/annotation.py, leaving `has_annotation` above it and `field_with_flag` below it intact. Delete the file tests/unit/cascade/test_extract_annotation.py entirely (`git rm` or Bash rm). Do NOT touch `has_annotation` or `field_with_flag` — `field_with_flag` is the production superseder still used in base.py:285 and elsewhere.
  </action>
  <verify>
    <automated>test -f tests/unit/cascade/test_extract_annotation.py && echo FAIL || true; grep -rn "extract_annotation" rapyer/ tests/ | (grep -v "^$" && echo "FAIL: refs remain" || echo "OK: no refs")</automated>
  </verify>
  <done>extract_annotation removed from rapyer/utils/annotation.py; test file deleted; grep finds zero references anywhere.</done>
</task>

<task type="auto">
  <name>Task 2: Add shared self-heal helper and wire all four FCALL execute sites</name>
  <files>rapyer/scripts/registry.py, rapyer/context.py, rapyer/base.py, rapyer/config.py, tests/integration/foreign_keys/test_cascade_ttl_apply.py</files>
  <action>
    In rapyer/scripts/registry.py add TWO module-level async helpers (place near run_fcall/arun_fcall; keep `from redis.exceptions import ... ResponseError` and `PersistentCascadeFunctionError` imports, already present):

    (a) `aretry_fcall_after_missing_function(redis_config, commands_backup)` — the reusable retry core. Call `await handle_missing_function(redis_config.redis, redis_config)` to FUNCTION LOAD and rewrite `redis_config.cascade_function_name`. Then read the (possibly new) name and rebuild ONLY the FCALL commands from `commands_backup` in a fresh transactional pipeline (`async with redis_config.redis.pipeline(transaction=True) as retry_pipe:`), rewriting each command's function name to the reloaded name: for each `(args, options)` where `args[0] == "FCALL"`, issue `retry_pipe.execute_command(args[0], redis_config.cascade_function_name, *args[2:], **options)` (mirrors arun_fcall's re-read-name semantics so a hash-changed plan still resolves). `try: return await retry_pipe.execute() except ResponseError as e: raise PersistentCascadeFunctionError("Cascade function still missing after re-loading. This indicates a server-side problem with Redis.") from e`.

    (b) `aexecute_pipeline_with_cascade_self_heal(pipe, redis_config)` — the shared execute wrapper for the three bare-execute sites. Back up `commands_backup = list(pipe.command_stack)`; `try: return await pipe.execute()`; `except ResponseError as e:` — if `"function not found" not in str(e).lower(): raise` (case-insensitive, mirrors arun_fcall); otherwise `return await aretry_fcall_after_missing_function(redis_config, commands_backup)`. This is a transparent pass-through for any pipeline that does not raise function-not-found (e.g. all fakeredis pipelines, all non-cascade pipelines).

    Add a short `"""..."""` docstring (own line, per style) to each only if the name is not self-evident; prefer the names carrying meaning.

    Wire the four sites:
    - rapyer/context.py `ensure_pipeline` (line ~61): replace `await pipe.execute()` with `await scripts_registry.aexecute_pipeline_with_cascade_self_heal(pipe, meta)`. Add a LAZY import inside the function: `from rapyer.scripts import registry as scripts_registry` (see <cycle_note> — module-top import here is a hard cycle). Reference it in the SAME edit as the import so the ruff hook does not strip it.
    - rapyer/context.py `pipeline_with_execution` (line ~68): same replacement + same lazy import inside that function.
    - rapyer/base.py `aset_ttl` (line ~631): replace `results = await pipe.execute()` with `results = await scripts_registry.aexecute_pipeline_with_cascade_self_heal(pipe, self.Meta)` (base.py already imports `scripts_registry`). `results[-1]` still holds the FCALL dangling-count return in both happy and retry paths. Remove the `# NOTE: bare execute -- no self-heal yet ... issue #284` comment (base.py:630).
    - rapyer/base.py `_apipeline` (lines ~1394-1428): extend the existing `except ResponseError as exc:` branch. When NOT `ignore_redis_error` AND `"function not found" in str(exc).lower()`, set a flag and (mirroring the NOSCRIPT block structure) call `await scripts_registry.aretry_fcall_after_missing_function(_meta, commands_backup)` — which reloads + replays the FCALL commands and raises PersistentCascadeFunctionError on repeat failure. Keep the existing NOSCRIPT/EVALSHA self-heal untouched; keep the plain `raise` for non-function ResponseErrors when not ignoring.

    Cleanup comments:
    - Remove the `# No self-heal in-pipeline ... issue #284` comment on `run_fcall` (registry.py:159); replace with a one-line note that self-heal now happens at execute time via aexecute_pipeline_with_cascade_self_heal (or drop it).
    - Update rapyer/config.py:83-85 comment: replace "arun_fcall's self-heal path rewrites" with "the cascade self-heal path (handle_missing_function) rewrites".
    - Remove the resolved issue-#284 NOTE block at tests/integration/foreign_keys/test_cascade_ttl_apply.py:183-187 (the whole trailing comment block).

    Do NOT change any fakeredis EXPIRE branch. Preserve single-FCALL atomicity.
  </action>
  <verify>
    <automated>uv run ruff check rapyer/ && uv run black --check rapyer/ && grep -rn "issue #284\|no self-heal\|arun_fcall's self-heal" rapyer/ tests/integration/foreign_keys/test_cascade_ttl_apply.py | (grep . && echo "FAIL: stale #284 refs" || echo "OK")</automated>
  </verify>
  <done>Two shared helpers exist in registry.py; all four execute sites route FCALL execution through them (no duplicated retry logic); base.py:630, registry.py:159, config.py:84, and the test note block updated/removed; fakeredis branches unchanged; ruff/black clean.</done>
</task>

<task type="auto">
  <name>Task 3: Remove redundant arun_fcall and rewrite the 3 integration helpers</name>
  <files>rapyer/scripts/registry.py, rapyer/scripts/__init__.py, tests/integration/foreign_keys/test_cascade_ttl_apply.py, tests/integration/foreign_keys/test_cascade_depth_and_gate.py, tests/integration/foreign_keys/test_cascade_graph_shapes.py</files>
  <action>
    Now that the pipeline path self-heals (Task 2), `arun_fcall` is production-redundant (planning grep confirms its only callers are the 3 integration test helpers). Delete the `arun_fcall` function from rapyer/scripts/registry.py. KEEP `handle_missing_function` and `PersistentCascadeFunctionError` — both are used by Task 2's self-heal. If — and only if — you find a genuine production consumer of arun_fcall after Task 2, keep it and document why in the SUMMARY instead of deleting.

    In rapyer/scripts/__init__.py remove `arun_fcall` from both the `from rapyer.scripts.registry import (...)` block and the `__all__` list.

    Rewrite the `_apply_cascade` helper in each of the 3 integration test files to invoke the function directly (remove the `from rapyer.scripts import arun_fcall` import from each, in the same edit as removing its use so the ruff hook is satisfied):
    - test_cascade_ttl_apply.py `_apply_cascade(real_redis_client, root)` -> `return await real_redis_client.fcall(type(root).Meta.cascade_function_name, 1, root.key, type(root).__name__, SPECIAL_FIELD_KEY_PREFIX, type(root).Meta.ttl, 1)`. Also rewrite the inline `arun_fcall(...)` call at line ~161 (uses ROOT_TTL_SECONDS and parent) to the same `real_redis_client.fcall(parent.Meta.cascade_function_name, 1, parent.key, type(parent).__name__, SPECIAL_FIELD_KEY_PREFIX, ROOT_TTL_SECONDS, 1)` form.
    - test_cascade_depth_and_gate.py `_apply_cascade(real_redis_client, root, cascade=True)` -> `return await real_redis_client.fcall(type(root).Meta.cascade_function_name, 1, root.key, type(root).__name__, SPECIAL_FIELD_KEY_PREFIX, type(root).Meta.ttl, 1 if cascade else 0)`.
    - test_cascade_graph_shapes.py `_apply_cascade(real_redis_client, root)` -> same direct-fcall form as ttl_apply.

    Keep `SPECIAL_FIELD_KEY_PREFIX` imports (still used). Preserve every existing assertion — these helpers must behave identically (fcall return shape is unchanged from arun_fcall's happy path).
  </action>
  <verify>
    <automated>grep -rn "arun_fcall" rapyer/ tests/ | (grep . && echo "FAIL: arun_fcall refs remain" || echo "OK: removed"); uv run ruff check rapyer/ tests/integration/foreign_keys/ && uv run black --check rapyer/ tests/integration/foreign_keys/</automated>
  </verify>
  <done>arun_fcall deleted from registry.py and __init__.py (import + __all__); handle_missing_function and PersistentCascadeFunctionError retained; 3 test helpers call real_redis_client.fcall directly; zero arun_fcall references remain; ruff/black clean.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 4: Integration regression test proving production self-heal (issue #284)</name>
  <files>tests/integration/foreign_keys/test_cascade_self_heal.py</files>
  <behavior>
    - After the cascade function is registered and then dropped (FUNCTION FLUSH), a production TTL-refresh call (aset_ttl cascade=True, or refresh_ttl) transparently reloads the function and still refreshes the whole reachable subtree's TTLs.
    - The call does NOT raise (proves self-heal, not just a re-register-before-call).
    - Meta.cascade_function_name is repopulated after the self-heal (handle_missing_function rewrote it).
  </behavior>
  <action>
    Create tests/integration/foreign_keys/test_cascade_self_heal.py (real Redis on :6370). Use `pytestmark = pytest.mark.usefixtures("setup_real_redis_for_cascade_apply")` (the fixture registers the cascade function and swaps cascade models onto the real client). Reuse the CascadeSpecialParent/CascadeSpecialChild model shape from tests/models/cascade_types (as in test_cascade_ttl_apply.py).

    Test flow:
    1. Save child (`await CascadeSpecialChild().asave()`, add a `tags` member and a `scores` entry) and parent (`await CascadeSpecialParent(child=child.key).asave()`); `persist` all keys (parent, child, tags special key, scores special key) so only the cascade can bring TTLs back.
    2. Drop the function: `await real_redis_client.function_flush()` (or FUNCTION DELETE the library). Assert the raw FCALL now fails — `with pytest.raises(...): await real_redis_client.fcall(type(parent).Meta.cascade_function_name, 1, parent.key, ...)` — to prove the function is genuinely gone (RED baseline). Use a fresh dummy call OR skip this sub-assert if it would consume the reload; simplest: assert via a direct fcall that it raises "function not found", then function_flush again if needed. (Prefer: flush, then go straight to step 3 and let the assertion in step 4 prove recovery.)
    3. Invoke the PRODUCTION path: `await parent.aset_ttl(ROOT_TTL_SECONDS, cascade=True)` (this enqueues the FCALL and executes it via aexecute_pipeline_with_cascade_self_heal). It must NOT raise.
    4. Assert the reachable subtree refreshed: `await real_redis_client.ttl(parent.key) > 0`, and for child.key + the two special keys the ttl is > 0 (child subtree re-armed to child's Meta.ttl). Assert `type(parent).Meta.cascade_function_name is not None` after the call.

    Add a second test hitting `refresh_ttl` directly (`await parent.refresh_ttl()`) after a function_flush to cover the pipeline_with_execution execute site as well. Keep helper names self-explanatory; no docstrings unless a name cannot convey intent.
  </action>
  <verify>
    <automated>uv sync --extra test --group dev >/dev/null 2>&1; uv run pytest tests/integration/foreign_keys/test_cascade_self_heal.py -x -q</automated>
  </verify>
  <done>New test passes on real Redis (:6370): after FUNCTION FLUSH, aset_ttl(cascade=True) and refresh_ttl transparently reload the cascade function and refresh the reachable subtree; cascade_function_name is repopulated; the call does not raise.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| app -> Redis server | Cascade FCALL crosses into server-side Lua; the loaded library defines the trust surface |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-luc-01 | Tampering | Replayed FCALL args after reload | mitigate | Rewrite only the function-name slot (args[1]) to the reloaded name; keep numkeys/keys/args verbatim from command_stack backup — no user input re-parsing |
| T-luc-02 | Denial of Service | Infinite reload/retry loop | mitigate | Retry exactly ONCE; second function-not-found raises PersistentCascadeFunctionError (mirrors PersistentNoScriptError) |
| T-luc-03 | Repudiation | Silent swallow of non-function ResponseError | accept | Non-"function not found" ResponseErrors re-raise unchanged; ignore_redis_error path in _apipeline is unchanged behavior |
| T-luc-SC | Tampering | npm/pip/cargo installs | accept | No new dependencies added; no package installs in this plan |
</threat_model>

<verification>
- Full fakeredis unit suite passes: `uv run pytest tests/unit -q` (confirms no regression from dead-code removal and the pass-through self-heal helper on fakeredis pipelines).
- Cascade integration suite passes on :6370: `uv run pytest tests/integration/foreign_keys -q`.
- Lint/format/type clean: `uv run ruff check .`, `uv run black --check .`, and `tox -e mypy` (scoped to tests/models) unaffected.
- No references remain to `extract_annotation`, `arun_fcall`, or "issue #284" in rapyer/ or the cascade tests.
</verification>

<success_criteria>
- extract_annotation + its test deleted; zero references.
- Single shared self-heal helper reused by all four FCALL execute sites; retry logic not duplicated.
- arun_fcall removed (import + __all__ + 3 test helpers rewritten to client.fcall); handle_missing_function + PersistentCascadeFunctionError retained.
- fakeredis EXPIRE branch and existing Meta.ttl/refresh_ttl behavior unchanged; single-FCALL atomicity preserved.
- New self-heal integration test passes on real Redis, proving transparent reload + subtree refresh after FUNCTION FLUSH.
- All resolved issue-#284 TODO comments removed (base.py:630, registry.py:159, config.py:84 comment updated, test note block removed).
- ruff/black clean; fakeredis unit suite + cascade integration suite green.
</success_criteria>

<output>
Create `.planning/quick/260720-luc-remove-dead-cascade-helpers-and-wire-284/260720-luc-SUMMARY.md` when done.
</output>
