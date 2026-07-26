---
type: quick
slug: hc2-cascade-plan-redis-key
branch: cascade-ttl-full-review
base_commit: 7d1e01e
autonomous: true
files_modified:
  - rapyer/types/special.py
  - rapyer/cascade/planner.py
  - rapyer/scripts/lua/cascade/apply.lua
  - rapyer/init.py
  - rapyer/base.py
  - tests/integration/conftest.py
  - tests/integration/foreign_keys/conftest.py
  - tests/unit/cascade/conftest.py
  - tests/integration/foreign_keys/test_cascade_ttl_apply.py
  - tests/integration/foreign_keys/test_cascade_graph_shapes.py
  - tests/unit/cascade/test_cascade_apply_lua.py
  - tests/unit/cascade/test_cascade_apply_lua_syntax.py
  - tests/unit/cascade/test_aset_ttl_cascade_flag.py
  - tests/unit/cascade/test_refresh_ttl_cascade_branch.py
  - tests/unit/cascade/test_cascade_action_boundary.py
  - tests/unit/cascade/test_cascade_plan_injection.py
  - tests/unit/test_init_rapyer.py
---

<objective>
Replace per-call ARGV delivery of the cascade plan with a single server-side Redis key.

Today each model caches its reachable plan subset on `_cascade_plan_arg` and ships it
as ARGV[5] on every EVALSHA. Write the FULL plan ONCE to a Redis key at `init_rapyer`;
the Lua `GET`s + `cjson.decode`s it each call. Per call we send only the ~24-byte key
NAME as ARGV[5], not the plan.

DESIGN IS DECIDED. Do NOT reintroduce reachable-subset delivery. The user explicitly
chose "one full-plan key", accepting decode is O(all registered) again (CodSpeed measured
afterward).

Output: cascade plan lives in one Redis key `__rapyer_cascade_plan__`; `_cascade_plan_arg`
and `reachable_plan_subset` deleted repo-wide.
</objective>

<context>
@rapyer/cascade/planner.py
@rapyer/scripts/lua/cascade/apply.lua
@rapyer/init.py
@rapyer/base.py
@rapyer/types/special.py

Constraints (project style): module-top imports only (no in-function imports except to
break a real cycle); WHY-only comments, short, no workflow tags; no docstrings-for-docs;
`black` + `ruff` clean.

Confirmed facts:
- `special.py:7` — `SPECIAL_FIELD_KEY_PREFIX = "__rapyer_special__"`.
- `planner.py:280-307` — `reachable_plan_subset` (REMOVE). `cascade_plan_json` (`:323`)
  serializes any `dict[str, CascadePlanEntry]` — works on the full plan unchanged (KEEP).
  `build_cascade_plan`/`validate_cascade_ttl_targets` stay.
- `apply.lua:1-10` — comment block + `local CASCADE_PLAN = cjson.decode(ARGV[5] or '{}')`
  then `local classes = CASCADE_PLAN`. Everything downstream indexes `classes[name]`.
- `init.py:9-14` imports incl. `reachable_plan_subset`; `:84-91` builds plan and caches
  `_cascade_plan_arg` per model inside the try; `:98-99` bottom `if redis is not None:`
  calls `register_scripts`.
- `base.py:87` `from rapyer.types.special import SPECIAL_FIELD_KEY_PREFIX, SpecialFieldType`;
  `:176` `_cascade_plan_arg: ClassVar[str] = "{}"`; `:269` and `:619` pass
  `self._cascade_plan_arg` as final `run_sha` arg (after `SPECIAL_FIELD_KEY_PREFIX` at
  `:264`/`:616`).
- `test_init_rapyer.py` uses `mock_redis_client = AsyncMock(spec=Redis)` — `await
  redis.get(...)` returns a MagicMock, NOT JSON. Assert on `mock_redis_client.set`, never
  on `.get`; do NOT switch this suite to fakeredis.
- Fixtures flush at SETUP before the init-emulating fixtures run; writing the plan key
  after `register_scripts` survives into the test body. noscript tests use SCRIPT FLUSH
  (leaves data keys intact).
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add CASCADE_PLAN_KEY constant + remove reachable_plan_subset</name>
  <files>rapyer/types/special.py, rapyer/cascade/planner.py</files>
  <action>
  In `rapyer/types/special.py`, add `CASCADE_PLAN_KEY = "__rapyer_cascade_plan__"` next to
  `SPECIAL_FIELD_KEY_PREFIX` (line 7).

  In `rapyer/cascade/planner.py`, DELETE `reachable_plan_subset` (lines 280-307) entirely.
  KEEP `cascade_plan_json` unchanged in behavior, but fix its docstring/comment that says
  "reachable-plan subset ... shipped per call as ARGV[5]" — it now serializes the full plan
  written once to a Redis key. Remove any import left unused only by the deleted function
  (verify: `_drop_none_values`, `json`, `dataclasses` are still used by `cascade_plan_json`,
  so keep them).
  </action>
  <verify>
    <automated>grep -rn "reachable_plan_subset" rapyer/ | grep -c . ; test $(grep -rc "reachable_plan_subset" rapyer/ | awk -F: '{s+=$2} END{print s}') -eq 0 && grep -q 'CASCADE_PLAN_KEY = "__rapyer_cascade_plan__"' rapyer/types/special.py && echo OK</automated>
  </verify>
  <done>`CASCADE_PLAN_KEY` defined in special.py; `reachable_plan_subset` gone from planner.py; `cascade_plan_json` intact with corrected comment.</done>
</task>

<task type="auto">
  <name>Task 2: Lua reads plan from Redis key (ARGV[5] = key name)</name>
  <files>rapyer/scripts/lua/cascade/apply.lua</files>
  <action>
  Replace the ARGV[5] block (lines 4-10). Remove the comment claiming a reachable-plan
  subset is shipped per call. New body:

  A WHY comment explaining: the full cascade plan is written once to a Redis key at
  `init_rapyer` (its NAME is ARGV[5]) and read here, instead of shipped per call; a missing
  key (pre-init, or flushed) makes GET return false -> empty plan -> root-own-keys-only
  refresh.

  Then:
  - `local plan_raw = redis.call('GET', ARGV[5])`
  - `local CASCADE_PLAN = plan_raw and cjson.decode(plan_raw) or {}`
  - `local classes = CASCADE_PLAN`

  Lua truthiness: GET returns false for a missing key -> `{}`; a JSON string is truthy ->
  decoded. Nothing else in the script changes; ARGV[5] is now the key NAME.
  </action>
  <verify>
    <automated>grep -q "redis.call('GET', ARGV\[5\])" rapyer/scripts/lua/cascade/apply.lua && ! grep -q "cjson.decode(ARGV\[5\]" rapyer/scripts/lua/cascade/apply.lua && echo OK</automated>
  </verify>
  <done>Lua GETs ARGV[5] as a key, decodes on hit, degrades to `{}` on miss; `classes` alias preserved.</done>
</task>

<task type="auto">
  <name>Task 3: init_rapyer writes the plan key; base.py passes the key name</name>
  <files>rapyer/init.py, rapyer/base.py</files>
  <action>
  `rapyer/init.py`:
  - Imports: drop `reachable_plan_subset`; keep `build_cascade_plan`,
    `validate_cascade_ttl_targets`, `cascade_plan_json`; add `CASCADE_PLAN_KEY` (module-top,
    `from rapyer.types.special import CASCADE_PLAN_KEY`).
  - Remove the per-model `_cascade_plan_arg` caching loop (lines 86-91). Keep
    `plan = build_cascade_plan(REDIS_MODELS)` + `validate_cascade_ttl_targets(plan)` inside
    the try (lines 82-85); `plan` stays in scope after the try.
  - In the bottom `if redis is not None:` block, write the key BEFORE `register_scripts`:
    `await redis.set(CASCADE_PLAN_KEY, cascade_plan_json(plan))` then the existing
    `await register_scripts(redis, is_fake_redis)`.

  `rapyer/base.py`:
  - Add `CASCADE_PLAN_KEY` to the existing `from rapyer.types.special import (...)` at
    line 87.
  - DELETE the `_cascade_plan_arg` ClassVar (line 176).
  - In `refresh_ttl` (line 269) and `aset_ttl` (line 619), change the final `run_sha` arg
    from `self._cascade_plan_arg` to `CASCADE_PLAN_KEY`.
  - Update the WHY comment near those call sites: the full plan lives in one Redis key,
    read server-side; we pass only its name. NO `_has_cascade`-style branch; the script
    still ALWAYS runs; EVALSHA + atomicity + CascadeResult unchanged.
  </action>
  <verify>
    <automated>test $(grep -rc "_cascade_plan_arg" rapyer/ | awk -F: '{s+=$2} END{print s}') -eq 0 && grep -q "await redis.set(CASCADE_PLAN_KEY, cascade_plan_json(plan))" rapyer/init.py && grep -c "CASCADE_PLAN_KEY" rapyer/base.py | grep -qv '^0$' && python -c "import ast; ast.parse(open('rapyer/init.py').read()); ast.parse(open('rapyer/base.py').read())" && echo OK</automated>
  </verify>
  <done>`_cascade_plan_arg` gone from rapyer/; init writes the key before register_scripts; both run_sha call sites pass `CASCADE_PLAN_KEY`.</done>
</task>

<task type="auto">
  <name>Task 4: Update init-emulating fixtures to write the plan key</name>
  <files>tests/integration/conftest.py, tests/integration/foreign_keys/conftest.py, tests/unit/cascade/conftest.py</files>
  <action>
  Each fixture emulates `init_rapyer` and currently caches `_cascade_plan_arg` per model.
  In all three, replace that caching loop with a single write on the SAME client AFTER
  `register_scripts`:
  `await <client>.set(CASCADE_PLAN_KEY, cascade_plan_json(build_cascade_plan(<MODELS>)))`

  MODELS per file:
  - `tests/integration/conftest.py` (autouse `real_redis_client`): `REDIS_MODELS`.
  - `tests/integration/foreign_keys/conftest.py` (`setup_real_redis_for_cascade_apply`):
    `CASCADE_INTEGRATION_MODELS`.
  - `tests/unit/cascade/conftest.py` (`setup_fake_redis_for_cascade_apply`):
    `CASCADE_PLANNER_MODELS`.

  Imports in each: drop `reachable_plan_subset`; keep `build_cascade_plan` +
  `cascade_plan_json`; add `CASCADE_PLAN_KEY` (module-top). Update the stale comments that
  reference the "reachable subset per call via _cascade_plan_arg".

  The flush-at-setup ordering means the key written here survives into the test body.
  </action>
  <verify>
    <automated>test $(grep -rc "_cascade_plan_arg\|reachable_plan_subset" tests/integration/conftest.py tests/integration/foreign_keys/conftest.py tests/unit/cascade/conftest.py | awk -F: '{s+=$2} END{print s}') -eq 0 && grep -q "CASCADE_PLAN_KEY, cascade_plan_json(build_cascade_plan(REDIS_MODELS))" tests/integration/conftest.py && echo OK</automated>
  </verify>
  <done>All three fixtures write the full plan key after register_scripts; no `_cascade_plan_arg`/`reachable_plan_subset` refs remain in them.</done>
</task>

<task type="auto">
  <name>Task 5: Update tests that pass ARGV[5] or assert on the plan arg</name>
  <files>tests/integration/foreign_keys/test_cascade_ttl_apply.py, tests/integration/foreign_keys/test_cascade_graph_shapes.py, tests/unit/cascade/test_cascade_apply_lua.py, tests/unit/cascade/test_aset_ttl_cascade_flag.py, tests/unit/cascade/test_refresh_ttl_cascade_branch.py, tests/unit/cascade/test_cascade_action_boundary.py, tests/unit/cascade/test_cascade_apply_lua_syntax.py</files>
  <action>
  Direct-invocation helpers: in `test_cascade_ttl_apply.py` (lines 34, 177),
  `test_cascade_graph_shapes.py` (line 29), and `test_cascade_apply_lua.py` (line 47),
  the `_apply_cascade`/direct `run_sha` calls pass `..., type(root)._cascade_plan_arg` (or
  `type(parent)._cascade_plan_arg`) as the final arg. Change each to `CASCADE_PLAN_KEY`
  and import it (`from rapyer.types.special import CASCADE_PLAN_KEY`). The plan key itself
  is written by the corresponding init-emulating fixture (Task 4).

  Mock-based tests `test_aset_ttl_cascade_flag.py` (lines 58, 95, 132),
  `test_refresh_ttl_cascade_branch.py` (lines 38, 72), and `test_cascade_action_boundary.py`:
  the expected trailing `run_sha` arg (ARGV[5]) is now the constant `CASCADE_PLAN_KEY`, not
  `type(model)._cascade_plan_arg`. READ each assertion to get its exact form (some assert
  `call_args.args[...]`, some assemble a full expected arg tuple) and update accordingly;
  import `CASCADE_PLAN_KEY`. For `test_cascade_action_boundary.py`, confirm whether it
  actually asserts the trailing arg (it checks `call_args.args[1]` == script name) — only
  touch it if it references `_cascade_plan_arg`.

  `test_cascade_apply_lua_syntax.py`: currently asserts `"--[[CASCADE_PLAN_TABLE]]" not in
  text` and `"cjson.decode(ARGV[5]" in text`. Update the second assertion to match the new
  Lua: assert `"redis.call('GET', ARGV[5])" in text` (and, if kept, `"cjson.decode(plan_raw)"
  in text`). Keep the `--[[CASCADE_PLAN_TABLE]]`-absent assert and the `script_load` compile
  check.
  </action>
  <verify>
    <automated>test $(grep -rc "_cascade_plan_arg" tests/ | awk -F: '{s+=$2} END{print s}') -eq 0 && grep -q "redis.call('GET', ARGV\[5\])" tests/unit/cascade/test_cascade_apply_lua_syntax.py && echo OK</automated>
  </verify>
  <done>No `_cascade_plan_arg` refs remain in tests; syntax test greps the new Lua GET; direct-invocation and mock tests pass the `CASCADE_PLAN_KEY` constant.</done>
</task>

<task type="auto">
  <name>Task 6: Rework plan-injection and init tests; add degrade-path coverage</name>
  <files>tests/unit/cascade/test_cascade_plan_injection.py, tests/unit/test_init_rapyer.py, tests/integration/foreign_keys/test_cascade_ttl_apply.py, tests/unit/cascade/test_cascade_apply_lua.py</files>
  <action>
  `test_cascade_plan_injection.py`: drop the `reachable_plan_subset` import and its tests
  (lines 54-123). KEEP/expand `cascade_plan_json` tests: full-plan round-trip via
  `json.loads`; None depth/ttl omission; serializing full `build_cascade_plan` output
  contains every class. Keep AAA (Arrange/Act/Assert) comment markers.

  `test_init_rapyer.py` — this suite uses `mock_redis_client = AsyncMock(spec=Redis)`, so
  `await redis.get(...)` returns a MagicMock, NOT JSON. Do NOT switch to fakeredis and do
  NOT assert on `redis.get`. Two changes:
  - REWRITE `test_init_rapyer_caches_valid_cascade_plan_arg_per_model_sanity` (lines 253-265,
    reads `model._cascade_plan_arg`): after `await init_rapyer(mock_redis_client)`, assert on
    `mock_redis_client.set`. Find the awaited `set` call whose `args[0] == CASCADE_PLAN_KEY`
    (scan `mock_redis_client.set.await_args_list`; fall back to `call_args_list` if the mock
    records there), then `decoded = json.loads(that call's args[1])` and assert every
    registered class name in `redis_models` is in `decoded`. Rename to reflect the new
    guarantee (e.g. `test_init_rapyer_writes_full_cascade_plan_key_sanity`). Import
    `CASCADE_PLAN_KEY` (`from rapyer.types.special import CASCADE_PLAN_KEY`).
  - DELETE `test_init_rapyer_no_edge_model_ships_only_its_own_class_sanity` (lines 268-279)
    OUTRIGHT — do NOT patch it. Its assertion `decoded <= {NoneTestModel.__name__}` encodes
    the per-root reachable-subset guarantee we are deliberately abandoning (the full plan now
    holds every class), so it cannot be salvaged. Deleting it also removes the dead
    `_cascade_plan_arg` ref on line 278.
  - Keep the existing SF-only injection assertion (`script_load`-based test earlier in the
    file) untouched.

  New coverage — Fakeredis unit test (AAA) in `test_cascade_apply_lua.py` (or the plan-
  injection file, wherever the fake-redis cascade fixture is in scope): with
  `CASCADE_PLAN_KEY` DELETED (`await client.delete(CASCADE_PLAN_KEY)`), a cascade call does
  NOT raise and still refreshes the root's own main key (ttl > 0). Proves the `or {}`
  degrade path.

  New coverage — Real-Redis integration test in `test_cascade_ttl_apply.py`: the plan key
  is written at init (`GET CASCADE_PLAN_KEY` decodes to a dict containing all participant
  classes) AND a cascade root refreshes its whole reachable subtree sourced from the Redis
  key (assert child + special keys got their ttls).
  </action>
  <verify>
    <automated>test $(grep -rc "_cascade_plan_arg\|reachable_plan_subset" tests/ | awk -F: '{s+=$2} END{print s}') -eq 0 && grep -q "CASCADE_PLAN_KEY" tests/unit/test_init_rapyer.py && ! grep -q "test_init_rapyer_no_edge_model_ships_only_its_own_class_sanity" tests/unit/test_init_rapyer.py && echo OK</automated>
  </verify>
  <done>Plan-injection tests cover full-plan `cascade_plan_json`; init test asserts `mock_redis_client.set` wrote a plan containing every class (no `.get` on the mock); the reachable-subset no-edge test is DELETED; degrade-path (deleted key -> no raise, root refreshed) and full-plan-key integration test added.</done>
</task>

<task type="auto">
  <name>Task 7: Repo-wide cleanup grep + lint + full suite</name>
  <files>(verification only)</files>
  <action>
  Confirm zero `_cascade_plan_arg` and zero `reachable_plan_subset` references remain
  repo-wide (rapyer/ and tests/). Run `black --check` and `ruff check` on the touched files.
  Run the full suite against real Redis Stack on localhost:6370. Explicitly confirm the
  pre-existing dangling / graph-shape / depth-budget / noscript-recovery cascade tests pass.
  </action>
  <verify>
    <automated>test $(grep -rc "_cascade_plan_arg\|reachable_plan_subset" rapyer/ tests/ | awk -F: '{s+=$2} END{print s}') -eq 0 && black --check rapyer tests && ruff check rapyer tests && REDIS_DB=0 python -m pytest tests -q -p no:randomly</automated>
  </verify>
  <done>Zero stale refs; black + ruff clean; full suite 0 failures on Redis Stack :6370; cascade dangling/graph-shape/depth/noscript tests green.</done>
</task>

</tasks>

<verification>
- `grep -rc "_cascade_plan_arg\|reachable_plan_subset" rapyer/ tests/` sums to 0.
- `black --check` + `ruff check` clean on touched files.
- `REDIS_DB=0 python -m pytest tests -q -p no:randomly` (real Redis Stack on localhost:6370): 0 failures.
- Pre-existing dangling / graph-shape / depth-budget / noscript-recovery cascade tests pass.
</verification>

<success_criteria>
- Full cascade plan written ONCE to `__rapyer_cascade_plan__` at `init_rapyer` (before `register_scripts`).
- Lua `GET`s + decodes ARGV[5] as the key NAME; missing key degrades to root-own-keys-only refresh via `or {}`.
- `_cascade_plan_arg` ClassVar and `reachable_plan_subset` deleted repo-wide; NO reachable-subset delivery reintroduced.
- `cascade_plan_json`, `build_cascade_plan`, `validate_cascade_ttl_targets`, EVALSHA/atomicity/CascadeResult all unchanged.
- Script still ALWAYS runs (no `_has_cascade` branch).
</success_criteria>

<commit>
Single commit:
`perf(cascade): store the cascade plan in one Redis key read server-side instead of shipping it per call (PR #283 review)`

Trailer:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
</commit>
</content>
