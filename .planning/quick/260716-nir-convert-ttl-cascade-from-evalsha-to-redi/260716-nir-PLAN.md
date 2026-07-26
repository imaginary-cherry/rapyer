---
phase: quick-260716-nir
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - rapyer/scripts/constants.py
  - rapyer/cascade/planner.py
  - rapyer/scripts/lua/cascade/library.lua
  - rapyer/scripts/lua/cascade/apply.lua
  - rapyer/scripts/loader.py
  - rapyer/scripts/registry.py
  - rapyer/scripts/__init__.py
  - rapyer/errors/cascade.py
  - rapyer/errors/__init__.py
  - rapyer/init.py
  - rapyer/base.py
  - rapyer/types/special.py
  - tests/conftest.py
  - tests/unit/conftest.py
  - tests/unit/cascade/conftest.py
  - tests/unit/cascade/test_cascade_apply_lua.py
  - tests/unit/cascade/test_cascade_apply_lua_syntax.py
  - tests/unit/cascade/test_cascade_plan_injection.py
  - tests/unit/cascade/test_aset_ttl_cascade_flag.py
  - tests/unit/cascade/test_refresh_ttl_cascade_branch.py
  - tests/integration/conftest.py
  - tests/integration/foreign_keys/conftest.py
  - tests/integration/foreign_keys/test_cascade_ttl_apply.py
  - tests/integration/foreign_keys/test_cascade_action_boundary.py
  - tests/integration/foreign_keys/test_cascade_graph_shapes.py
  - tests/integration/foreign_keys/test_cascade_concurrent_mutation.py
  - docs/documentation/special-fields/ttl-cascade.md
  - .planning/codebase/CONCERNS.md
autonomous: true
requirements: [CASCADE-FN-01]

must_haves:
  truths:
    - "TTL cascade runs via a Redis Functions library (FUNCTION LOAD + FCALL), not EVALSHA."
    - "The cascade plan is baked into the library source and cjson.decode'd once at FUNCTION LOAD, not fetched per call."
    - "Two rapyer processes with different model sets against one server do not clobber each other's baked plan."
    - "A missing/flushed cascade function is transparently re-loaded and retried once on direct (arun_fcall) calls."
    - "On fakeredis, a root's own main + special keys still refresh via Meta.ttl/refresh_ttl; only cascade edge-following is disabled."
    - "Non-cascade Meta.ttl / refresh_ttl behavior is unchanged on both backends."
    - "Cascade traversal is proven only against real Redis 7+; non-cascade TTL stays dual-backend."
  artifacts:
    - path: "rapyer/scripts/lua/cascade/library.lua"
      provides: "Redis Functions library: baked plan upvalue + cascade_apply callback"
      contains: "register_function"
    - path: "rapyer/scripts/registry.py"
      provides: "FUNCTION LOAD REPLACE registration + FCALL invocation + missing-function retry"
      contains: "function_load"
    - path: "rapyer/cascade/planner.py"
      provides: "deterministic library/function name (plan hash) + Lua-literal plan serializer"
  key_links:
    - from: "rapyer/init.py"
      to: "rapyer/scripts/registry.py"
      via: "register_cascade_function on init (skipped on fakeredis)"
      pattern: "register_cascade_function"
    - from: "rapyer/base.py"
      to: "rapyer/scripts/registry.py"
      via: "run_fcall in refresh_ttl / aset_ttl (real redis), all_keys EXPIRE fallback (fakeredis)"
      pattern: "run_fcall"
---

<objective>
Convert TTL cascade from an EVALSHA Lua script to a Redis Functions library, and make TTL cascade real-Redis-7+-only (drop fakeredis support for the cascade traversal, while keeping the root's own TTL refresh working on fakeredis).

Purpose: A Redis Functions library lets the cascade plan be baked into the library source and decoded ONCE at FUNCTION LOAD (captured as an upvalue), removing the per-call plan GET+decode the current EVALSHA path does. This is the design already agreed with the user; this plan implements it — do not re-litigate the approach.

Output:
- New rapyer/scripts/lua/cascade/library.lua (Redis Functions library) replacing apply.lua.
- FUNCTION LOAD REPLACE registration + FCALL invocation machinery in the scripts layer (cascade only; all other scripts stay on EVALSHA).
- init_rapyer wiring that bakes the plan into the library and loads it (skipped on fakeredis).
- base.py call sites switched to FCALL on real Redis, with a root-own-keys EXPIRE fallback on fakeredis.
- Cascade tests moved/gated to real-Redis-7+-only; non-cascade TTL tests stay dual-backend.
- Docs + CONCERNS.md updated.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@CLAUDE.md
@.planning/STATE.md

# The current EVALSHA cascade script being converted (preserve every comment's reasoning):
@rapyer/scripts/lua/cascade/apply.lua

# Scripts layer being extended:
@rapyer/scripts/constants.py
@rapyer/scripts/loader.py
@rapyer/scripts/registry.py

# The Python planner that builds/serializes the cascade plan:
@rapyer/cascade/planner.py

# init lifecycle + the two product call sites:
@rapyer/init.py

<interfaces>
<!-- Contracts the executor needs; extracted from the codebase. Use directly, no re-exploration. -->

redis-py (locked 7.0.1) exposes both (verified this environment): Redis.function_load(code, replace=False) and Redis.fcall(function, numkeys, *keys_and_args); Pipeline.fcall(...) queues like pipeline.evalsha(...) and is returned positionally from pipe.execute().

Current EVALSHA invocation helpers (rapyer/scripts/registry.py):
- run_sha(pipeline, script_name, keys, *args) -> queues pipe.evalsha(sha, keys, *args)
- arun_sha(client, redis_config, script_name, keys, *args) -> evalsha + NOSCRIPT self-heal + retry once
- handle_noscript_error(redis_client, redis_config) -> re-registers all scripts
- get_script(script_name) -> sha lookup, raises ScriptsNotInitializedError

Current cascade call sites (rapyer/base.py) both queue into a pipeline:
- refresh_ttl (~line 250): run_sha(pipe, CASCADE_TTL_APPLY_SCRIPT_NAME, 1, self.key, type(self).__name__, SPECIAL_FIELD_KEY_PREFIX, self.Meta.ttl, 1, CASCADE_PLAN_KEY) — always cascade=1, returns None.
- aset_ttl (~line 596): same script, cascade flag = 1 if cascade else 0, plan key as last ARGV; reads results[-1] -> {dangling_children, dangling_special} into CascadeResult; honors in_outer_pipe early-return; bare pipe.execute() with an issue #284 no-self-heal NOTE.

Root-own-key helper (rapyer/base.py): self.all_keys (cached_property) -> _all_keys_for_key(self.key) = main key + every declared special-field key (class-based, recurses nested). Use for the fakeredis EXPIRE fallback (matches the Lua's class-based special_suffixes).

Plan serialization (rapyer/cascade/planner.py): cascade_plan_json(plan) -> compact JSON str. build_cascade_plan(models), validate_cascade_ttl_targets(plan) unchanged.

CASCADE_PLAN_KEY = "__rapyer_cascade_plan__" (rapyer/types/special.py) — becomes DEAD once the plan is baked into the library; removed in Task 4.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add deterministic cascade name + Lua-literal plan serializer (Python, no Redis)</name>
  <files>rapyer/scripts/constants.py, rapyer/cascade/planner.py</files>
  <action>
Add to constants.py: CASCADE_LIBRARY_PREFIX = "rapyer_cascade" and CASCADE_FUNCTION_PREFIX = "cascade_apply". Keep the existing CASCADE_TTL_APPLY_SCRIPT_NAME for now (Task 4 removes it once no caller references it).

Add to planner.py three pure functions (add hashlib at module top; json is already imported):
- cascade_plan_hash(plan_json) -> a short stable hex digest of the compact plan JSON (hashlib.sha1(plan_json.encode()).hexdigest()[:16]). Deterministic across processes for the same plan.
- cascade_names(plan_json) -> tuple (library_name, function_name): library_name = f"{CASCADE_LIBRARY_PREFIX}_{hash}", function_name = f"{CASCADE_FUNCTION_PREFIX}_{hash}".
- cascade_plan_lua_literal(plan_json) -> wrap the compact JSON in a Lua long-bracket string [==[ ... ]==] so it embeds verbatim in Lua source with no escaping.

CRITICAL isolation reasoning (put this in a comment on cascade_names): Redis Function NAMES are server-GLOBAL, not per-library — two libraries cannot both register a function called cascade_apply (the second FUNCTION LOAD errors). So BOTH the library name AND the registered function name carry the plan hash. That is what lets two rapyer processes with different model sets (e.g. CI workers) coexist against one server instead of clobbering each other's baked plan; identical plans hash-collide to the same names so FUNCTION LOAD REPLACE is idempotent. FCALL therefore targets the hashed function name, not a bare cascade_apply.

cascade_plan_lua_literal must reject a payload that could break out of the long bracket: cascade plan JSON contains only class names (Python identifiers), dotted $-paths, and special-field suffixes — none can contain ]==]. This is product code, so use a real guard, not assert: if "]==]" in plan_json: raise a RapyerError (reuse an existing cascade error or add one) explaining the Lua-literal-safety invariant.

No in-function imports (per MEMORY): import CASCADE_LIBRARY_PREFIX/CASCADE_FUNCTION_PREFIX from constants at module top.
  </action>
  <verify>
    <automated>cd /Users/yedidyakfir/Documents/rapyer && uv run python -c "from rapyer.cascade.planner import cascade_names, cascade_plan_lua_literal; a=cascade_names('{}'); b=cascade_names('{}'); assert a==b and a[0].startswith('rapyer_cascade_') and a[1].startswith('cascade_apply_'); lit=cascade_plan_lua_literal('{}'); assert lit.startswith('[==[') and lit.endswith(']==]'); print('ok')"</automated>
  </verify>
  <done>cascade_names is deterministic and hashes BOTH names; cascade_plan_lua_literal produces an escaping-free Lua long-bracket literal and rejects a payload containing the delimiter. Existing planner unit tests still pass.</done>
</task>

<task type="auto">
  <name>Task 2: Write the Redis Functions library + FUNCTION LOAD/FCALL machinery</name>
  <files>rapyer/scripts/lua/cascade/library.lua, rapyer/scripts/loader.py, rapyer/scripts/registry.py, rapyer/scripts/__init__.py, rapyer/errors/cascade.py, rapyer/errors/__init__.py</files>
  <action>
Create rapyer/scripts/lua/cascade/library.lua by converting apply.lua (Task 4 deletes apply.lua). PRESERVE EVERY comment's reasoning from apply.lua. Structure per the agreed design:
- First line MUST be the shebang: #!lua name=RAPYER_CASCADE_LIB (loader replaces the RAPYER_CASCADE_LIB token with the computed library name).
- LIBRARY SCOPE runs ONCE at FUNCTION LOAD, where redis.call is FORBIDDEN — this is exactly why the plan is baked into source instead of GET from a key. At library scope put: local UNBOUNDED = -1; the baked plan local CASCADE_PLAN = cjson.decode(RAPYER_CASCADE_PLAN_LITERAL) (the RAPYER_CASCADE_PLAN_LITERAL token is replaced by the Lua long-bracket literal); and PURE/STATIC helpers only. Add a comment: Redis Functions are registered SERVER-GLOBAL (not per-DB), hence the hashed library+function names.
- redis.register_function('RAPYER_CASCADE_FN', function(keys, args) ... end) (loader replaces RAPYER_CASCADE_FN with the computed function name). Signature maps keys[1]=root_key, args[1]=root_class, args[2]=special_prefix, args[3]=root_ttl, args[4]=do_cascade. The old plan-key ARGV is GONE (no per-call GET+decode).
- INSIDE THE CALLBACK (MUST be per-call to avoid leaking across FCALLs — hoisting these to library scope is a correctness bug): the MUTABLE state visited, pending_refresh, refresh_order, stack, and every closure that touches them (queue_refresh, queue_special_refresh, push_child, push_edges, plan_refresh_keys). Pure helpers that hold NO per-call mutable state (budget_is_larger, next_hop, read_reference_paths, fk_edges) may live at library scope taking params. When unsure, keep it inside the callback. The read-walk / budget / write-phase (EXPIRE loop) logic is otherwise IDENTICAL to apply.lua. The callback returns {dangling_children_count, dangling_special_count}. Convert ARGV[i]/KEYS[i] references to args[i]/keys[i]; tonumber(args[4]) ~= 0 keeps the do_cascade default semantics.

loader.py: add build_cascade_library(plan_json) -> tuple (library_name, function_name, source). Read library.lua via importlib.resources (mirror _load_template; it forces a .lua suffix so pass name "library"), then substitute the three tokens: RAPYER_CASCADE_LIB -> library_name, RAPYER_CASCADE_FN -> function_name, RAPYER_CASCADE_PLAN_LITERAL -> cascade_plan_lua_literal(plan_json). Do NOT run the SF-dispatch / VARIANTS substitution on it (cascade has no SF placeholder and no fakeredis variant — it never loads on fakeredis).

registry.py:
- Remove the ("cascade", "apply", CASCADE_TTL_APPLY_SCRIPT_NAME) entry from SCRIPT_REGISTRY (cascade is no longer an EVALSHA script).
- Add module global _CASCADE_FUNCTION_NAME: str | None = None.
- async def register_cascade_function(redis_client, plan_json): build via build_cascade_library, await redis_client.function_load(source, replace=True), store the function name in _CASCADE_FUNCTION_NAME. REPLACE makes re-init idempotent for the same plan and refreshes a changed plan.
- def get_cascade_function_name() -> str: return _CASCADE_FUNCTION_NAME or raise ScriptsNotInitializedError (mirror get_script).
- def run_fcall(pipeline, keys, *args): pipeline.fcall(get_cascade_function_name(), keys, *args). NO self-heal (matches the existing EVALSHA-in-pipeline path; see the issue #284 note in aset_ttl).
- async def arun_fcall(client, redis_config, keys, *args): direct call with missing-function self-heal — try await client.fcall(name, keys, *args); on redis.exceptions.ResponseError whose message contains "function not found" (case-insensitive), call handle_missing_function(client, redis_config), then retry ONCE; a second failure raises PersistentCascadeFunctionError.
- async def handle_missing_function(redis_client, redis_config): no-op when redis_config.is_fake_redis; otherwise rebuild the plan from REDIS_MODELS (build_cascade_plan + cascade_plan_json) and register_cascade_function. Importing rapyer.base.REDIS_MODELS at module top would create a cycle (base -> scripts -> base) — keep ONLY that import inside this function and add a comment saying it is inline solely to break the cycle (per MEMORY: inline imports allowed only to break a real cycle).

errors/cascade.py: add class PersistentCascadeFunctionError(RapyerError). Export it from errors/__init__.py (add to imports + __all__).

scripts/__init__.py: export register_cascade_function, get_cascade_function_name, run_fcall, arun_fcall (add to imports and __all__).

Follow CLAUDE.md: async names carry the a-prefix or verb (register_cascade_function/arun_fcall/handle_missing_function are I/O — acceptable analogs of existing register_scripts/handle_noscript_error); no docstrings unless the name cannot convey purpose; comment the non-obvious (server-global namespace, per-call state, cycle-breaking inline import).
  </action>
  <verify>
    <automated>cd /Users/yedidyakfir/Documents/rapyer && uv run python -c "from rapyer.scripts.loader import build_cascade_library; ln,fn,src=build_cascade_library('{\"A\":{\"ttl\":10,\"special_suffixes\":[],\"fks\":[]}}'); assert src.splitlines()[0]=='#!lua name='+ln, src.splitlines()[0]; assert 'register_function' in src and fn in src and 'RAPYER_CASCADE_PLAN_LITERAL' not in src and 'RAPYER_CASCADE_LIB' not in src; print('ok')" && uv run ruff check rapyer/scripts rapyer/errors</automated>
  </verify>
  <done>library.lua exists with the shebang, baked-plan upvalue, and cascade_apply callback holding all per-call mutable state; build_cascade_library substitutes all three tokens; registry exposes register_cascade_function / get_cascade_function_name / run_fcall / arun_fcall with a missing-function retry; cascade is dropped from the EVALSHA SCRIPT_REGISTRY.</done>
</task>

<task type="auto">
  <name>Task 3: Wire init_rapyer + base.py call sites; add fakeredis root-own fallback</name>
  <files>rapyer/init.py, rapyer/base.py</files>
  <action>
init.py: after validate_cascade_ttl_targets(plan) and the refreeze, in the `if redis is not None:` block: keep await register_scripts(redis, is_fake_redis) (EVALSHA scripts, unchanged — cascade no longer in that set). Then if NOT is_fake_redis: await register_cascade_function(redis, cascade_plan_json(plan)). On fakeredis SKIP loading the function entirely (fakeredis has no Redis Functions). Remove the CASCADE_PLAN_KEY import and its redis.set(...) write. Add a comment: TTL cascade traversal is real-Redis-7+-only; on fakeredis only the root's own keys refresh.

base.py refresh_ttl (~line 250): keep the `if self.Meta.ttl is None: return None` guard and the pipe context. Branch on self.Meta.is_fake_redis:
- Real Redis: scripts_registry.run_fcall(pipe, 1, self.key, type(self).__name__, SPECIAL_FIELD_KEY_PREFIX, self.Meta.ttl, 1) (cascade always on, as today). Drop the CASCADE_PLAN_KEY arg.
- fakeredis: queue pipe.expire(k, self.Meta.ttl) for k in self.all_keys (main + special keys, NO edge traversal), preserving the existing Meta.ttl/refresh_ttl contract for the root's own keys.
Return None either way.

base.py aset_ttl (~line 596): keep the top-level is_inner_model guard, the in_outer_pipe detection, and the ensure_pipeline(should_execute=False) context. Branch on self.Meta.is_fake_redis:
- Real Redis: scripts_registry.run_fcall(pipe, 1, self.key, type(self).__name__, SPECIAL_FIELD_KEY_PREFIX, ttl, 1 if cascade else 0). Preserve the in_outer_pipe early-return, the bare pipe.execute() (keep the issue #284 no-self-heal NOTE), and results[-1] -> CascadeResult(dangling_children, dangling_special) for cascade / None for non-cascade.
- fakeredis: queue pipe.expire(k, ttl) for k in self.all_keys; if not in_outer_pipe: await pipe.execute(). Return None when cascade is False (unchanged contract); when cascade is True return CascadeResult(dangling_children=0, dangling_special=0) with a comment that cascade edge-following is a no-op on fakeredis (only the root's own keys refresh) — divergence recorded in CONCERNS.md (Task 5).

Update base.py imports: drop CASCADE_TTL_APPLY_SCRIPT_NAME and CASCADE_PLAN_KEY if now unused (keep SPECIAL_FIELD_KEY_PREFIX). Do not touch atomic_get_or_create or any other EVALSHA path. Preserve the @mark_actions decorator on aset_ttl (ActionGroup.UPDATE, ignore_refresh=True) and the a-prefix convention.
  </action>
  <verify>
    <automated>cd /Users/yedidyakfir/Documents/rapyer && uv run python -c "import inspect, rapyer.base as b; s=inspect.getsource(b.AtomicRedisModel.refresh_ttl)+inspect.getsource(b.AtomicRedisModel.aset_ttl); assert 'run_fcall' in s and 'is_fake_redis' in s and 'CASCADE_PLAN_KEY' not in s; import rapyer.init; print('ok')" && uv run ruff check rapyer/init.py rapyer/base.py</automated>
  </verify>
  <done>init_rapyer loads the cascade function on real Redis and skips it on fakeredis; refresh_ttl and aset_ttl FCALL on real Redis and fall back to all_keys EXPIRE on fakeredis; CASCADE_PLAN_KEY is no longer written or passed; other EVALSHA paths untouched.</done>
</task>

<task type="auto">
  <name>Task 4: Migrate + gate cascade tests to real-Redis-7+; remove dead EVALSHA cascade plumbing</name>
  <files>tests/conftest.py, tests/unit/conftest.py, tests/unit/cascade/conftest.py, tests/unit/cascade/test_cascade_apply_lua.py, tests/unit/cascade/test_cascade_apply_lua_syntax.py, tests/unit/cascade/test_cascade_plan_injection.py, tests/unit/cascade/test_aset_ttl_cascade_flag.py, tests/unit/cascade/test_refresh_ttl_cascade_branch.py, tests/integration/conftest.py, tests/integration/foreign_keys/conftest.py, tests/integration/foreign_keys/test_cascade_ttl_apply.py, tests/integration/foreign_keys/test_cascade_action_boundary.py, tests/integration/foreign_keys/test_cascade_graph_shapes.py, tests/integration/foreign_keys/test_cascade_concurrent_mutation.py, rapyer/scripts/lua/cascade/apply.lua, rapyer/scripts/constants.py, rapyer/types/special.py</files>
  <action>
Goal: every cascade-TRAVERSAL test runs only against real Redis 7+; every NON-cascade Meta.ttl/refresh_ttl test stays dual-backend; no test silently drops. Then delete the now-dead EVALSHA cascade plumbing.

Redis 7+ gate: in tests/integration/conftest.py add a session/module fixture (e.g. requires_redis_functions) that reads INFO server redis_version and pytest.skip(...) if < 7.0 (Redis Functions require 7.0). Apply it to the cascade integration modules (via pytestmark or fixture dependency). Add a clear skip reason: "TTL cascade requires Redis 7+ (Redis Functions)".

Move fakeredis cascade-traversal tests to real Redis:
- tests/unit/cascade/test_cascade_apply_lua.py and test_cascade_plan_injection.py currently exercise the cascade Lua under fakeredis via setup_fake_redis_for_cascade_apply + arun_sha(CASCADE_TTL_APPLY_SCRIPT_NAME, ...). Port their assertions to real Redis using arun_fcall (get_cascade_function_name) and a real-redis fixture that calls register_cascade_function with the built plan. Prefer relocating them under tests/integration/foreign_keys/ (mirroring test_cascade_ttl_apply.py) rather than deleting — do NOT lose coverage. If a behavior is already covered by an existing integration test, note that in a comment and drop the redundant duplicate rather than silently deleting.
- test_cascade_apply_lua_syntax.py: replace the EVALSHA-syntax check with a FUNCTION LOAD syntax check — build_cascade_library(...) then function_load(source, replace=True) on a real Redis 7+ client (guarded by the version gate) asserting no error. If the file only made sense for EVALSHA, replace it wholesale.
- test_aset_ttl_cascade_flag.py / test_refresh_ttl_cascade_branch.py: split — keep the NON-cascade (root-own-keys) assertions running on fakeredis (they now exercise the all_keys EXPIRE fallback); move the cascade=True / edge-traversal assertions to real Redis 7+.

Update conftests to the new plumbing:
- tests/integration/conftest.py real_redis_client fixture and tests/integration/foreign_keys/conftest.py setup_real_redis_for_cascade_apply: replace the CASCADE_PLAN_KEY write (redis.set(CASCADE_PLAN_KEY, cascade_plan_json(...))) with await register_cascade_function(redis, cascade_plan_json(build_cascade_plan(<models>))). Remove CASCADE_PLAN_KEY imports.
- tests/unit/cascade/conftest.py: setup_fake_redis_for_cascade_apply currently registers scripts + writes CASCADE_PLAN_KEY for the cascade Lua. Since cascade no longer runs on fakeredis, either drop this fixture (if its only consumers moved to integration) or repurpose it to only wire Meta.redis/is_fake_redis for the fallback tests. Remove the CASCADE_PLAN_KEY write.
- tests/unit/conftest.py fake_redis_client: register_scripts(is_fakeredis=True) stays (EVALSHA scripts); it no longer needs cascade. No cascade function load on fakeredis.

Delete dead plumbing (only after the above no longer references it):
- rapyer/scripts/lua/cascade/apply.lua (replaced by library.lua).
- CASCADE_TTL_APPLY_SCRIPT_NAME from rapyer/scripts/constants.py.
- CASCADE_PLAN_KEY from rapyer/types/special.py (and any lingering imports).
Grep the whole repo for CASCADE_PLAN_KEY, CASCADE_TTL_APPLY_SCRIPT_NAME, and apply.lua to confirm zero remaining references (excluding .planning/).

Watch the save-hook: add each new import together with its first use in the same edit (ruff --fix strips unused imports on save).
  </action>
  <verify>
    <automated>cd /Users/yedidyakfir/Documents/rapyer && ! grep -rn "CASCADE_PLAN_KEY\|CASCADE_TTL_APPLY_SCRIPT_NAME" rapyer/ tests/ ; test ! -f rapyer/scripts/lua/cascade/apply.lua && echo "dead-plumbing-gone"</automated>
    <automated>cd /Users/yedidyakfir/Documents/rapyer && REDIS_DB=0 uv run pytest tests/unit -q 2>&1 | tail -15</automated>
  </verify>
  <done>Cascade-traversal tests run only on real Redis 7+ (version-gated with a clear skip); non-cascade TTL tests remain dual-backend and pass on fakeredis via the all_keys fallback; apply.lua, CASCADE_TTL_APPLY_SCRIPT_NAME, and CASCADE_PLAN_KEY are fully removed with zero remaining references; unit suite green. (Full green requires a real Redis 7+ for the integration cascade tests.)</done>
</task>

<task type="auto">
  <name>Task 5: Update docs + CONCERNS.md</name>
  <files>docs/documentation/special-fields/ttl-cascade.md, .planning/codebase/CONCERNS.md</files>
  <action>
ttl-cascade.md: add a prominent note (near the top and/or an "Requirements / Limitations" section) that TTL cascade requires real Redis 7+ (it is implemented as a Redis Functions library, FUNCTION LOAD + FCALL) and is NOT supported under fakeredis. State the fakeredis behavior explicitly: on fakeredis a cascade-enabled model still refreshes its OWN main + special keys per Meta.ttl/refresh_ttl, but edges are NOT followed (no traversal); aset_ttl(cascade=True) refreshes only the root's own keys and reports zero danglings. If the doc mentions the dual fakeredis/real-Redis test strategy, clarify cascade is real-Redis-only.

CONCERNS.md: add entries recording the deliberate fakeredis divergences introduced here:
- TTL cascade traversal is real-Redis-7+-only (Redis Functions); fakeredis path refreshes root-own keys only.
- aset_ttl(cascade=True) on fakeredis silently returns CascadeResult(0,0) without following edges — a behavior divergence a fakeredis-only test could not catch; cascade correctness is covered by real-Redis integration tests only.
- Redis Functions are registered SERVER-GLOBAL; the library+function names are plan-hashed so concurrent processes/CI workers with different model sets do not clobber each other's baked plan.
  </action>
  <verify>
    <automated>cd /Users/yedidyakfir/Documents/rapyer && grep -qi "redis 7\|redis functions\|fcall\|function load" docs/documentation/special-fields/ttl-cascade.md && grep -qi "cascade" .planning/codebase/CONCERNS.md && echo "docs-ok"</automated>
  </verify>
  <done>Docs state the Redis 7+ / not-on-fakeredis requirement and the exact fakeredis fallback behavior; CONCERNS.md records the fakeredis divergence and the server-global function-namespace mitigation.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Python -> Lua library source | The cascade plan (class names, paths, suffixes, ttls) is baked into Lua source text at FUNCTION LOAD. |
| rapyer process -> shared Redis server | Redis Functions are server-global; multiple processes load libraries into one namespace. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-nir-01 | Tampering | cascade_plan_lua_literal baking JSON into Lua source | mitigate | Wrap in `[==[ ... ]==]` long bracket + product-code guard rejecting any payload containing `]==]`; plan JSON is identifier/path/suffix data only (no free-form user strings). |
| T-nir-02 | Tampering/DoS | server-global Redis Function namespace clobber | mitigate | Library AND function names carry the plan hash (cascade_names); FUNCTION LOAD REPLACE is idempotent per plan; concurrent differing plans coexist under distinct hashed names. |
| T-nir-03 | Denial of Service | missing/flushed cascade function mid-run | mitigate | arun_fcall catches "function not found" ResponseError, re-loads via handle_missing_function, retries once, else raises PersistentCascadeFunctionError. |
| T-nir-SC | Tampering | npm/pip/cargo installs | n/a | No new packages added (uses redis-py function_load/fcall already present at locked 7.0.1). |
</threat_model>

<verification>
- uv run ruff check . and uv run black --check . pass on all changed files.
- Repo grep confirms zero references to CASCADE_PLAN_KEY, CASCADE_TTL_APPLY_SCRIPT_NAME, or apply.lua (excluding .planning/).
- Unit suite green on fakeredis (non-cascade TTL + root-own fallback).
- On a real Redis 7+ (REDIS_DB set): cascade integration tests pass; on Redis < 7 they skip with the documented reason (not fail).
- No EVALSHA path other than cascade changed; atomic_get_or_create and numeric/string/dict/datetime scripts still register and run.
</verification>

<success_criteria>
- TTL cascade runs via FUNCTION LOAD + FCALL with the plan baked into the library and decoded once at load.
- Concurrent processes with different model sets do not clobber each other (hashed library+function names).
- Meta.ttl / refresh_ttl unchanged on both backends; cascade edge-following disabled on fakeredis with root-own keys still refreshing.
- Cascade tests real-Redis-7+-only and version-gated; non-cascade TTL dual-backend; no coverage silently dropped.
- Docs + CONCERNS.md updated.
</success_criteria>

<output>
Create .planning/quick/260716-nir-convert-ttl-cascade-from-evalsha-to-redi/260716-nir-SUMMARY.md when done.
</output>
