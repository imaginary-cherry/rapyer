# Codebase Concerns

**Analysis Date:** 2026-07-06

## Tech Debt

**ForeignKey/RelationalFieldType name-normalization hack:**
- Issue: The metaclass (`AtomicRedisModel.__init_subclass__`) converts a `ForeignKey`'s generic target into a dynamic per-field subclass, so target resolution has to fall back to matching by `__name__` against the global `REDIS_MODELS` registry instead of holding a static type reference.
- Files: `rapyer/types/foreign_key.py:141-146`, `rapyer/types/relational.py:59-80`
- Impact: Two models with a colliding class name across resolution paths, or any refactor of the metaclass's per-field-subclass strategy, can silently break relational target resolution (`_resolve_target_model`). Tracked upstream: `https://github.com/imaginary-cherry/rapyer/issues/247`.
- Fix approach: Keep reference targets as static types rather than metaclass-generated per-field subclasses (per the TODO), then drop the name-based lookup in favor of direct type identity.

**Backward-compatibility shim for a typo'd exception name:**
- Issue: `UnsupportArgumentTypeError` (missing "ed") is kept as a deprecated alias for `UnsupportedArgumentTypeError` via module `__getattr__`.
- Files: `rapyer/errors/__init__.py:28-37`
- Impact: Minor; dead code path scheduled for removal.
- Fix approach: Remove in 1.4.0 as the inline `# TODO` states.

**`AtomicRedisModel` is a large, multi-responsibility class:**
- Issue: A single 1331-line file/class owns key resolution, TTL refresh, index management, pipelining, locking, find/delete, atomic get-or-create, and the `__init_subclass__` metaprogramming that rewrites annotations into Redis-aware types.
- Files: `rapyer/base.py` (whole file; metaprogramming block at `rapyer/base.py:322-445`)
- Impact: High blast radius for any change — modifying field-classification logic in `__init_subclass__` can silently affect TTL, special-field detection, and foreign-key detection at once (see "Fragile Areas" below).
- Fix approach: Not urgent given current test coverage, but any cascade/TTL/table-like feature should be added as new, narrowly-scoped methods/mixins rather than growing `__init_subclass__` further.

**Dual v1/v2 action-wrapping code paths kept side by side:**
- Issue: `mark_actions(version=MarkVersion.V1|V2)` maintains two separate dedup/refresh strategies (`_build_seen_v1`/`_build_seen_v2`, `refresh_models_v1`/`refresh_models_v2`, `FLUSH_V1`/`FLUSH_V2`) purely for backward compatibility; V2 is the default and V1 exists mainly for legacy per-call re-checking.
- Files: `rapyer/actions.py:122-176`, `rapyer/actions.py:251-303`
- Impact: Two code paths to reason about and test whenever TTL/action semantics change; a new decorated method that unintentionally passes `version=MarkVersion.V1` gets different (slower, per-call) refresh semantics than the rest of the codebase.
- Fix approach: Deprecate/remove V1 once no internal call sites depend on it (verify via `grep -rn "MarkVersion.V1" rapyer/`).

**`RedisPriorityQueue` explicitly labeled Beta:**
- Issue: CHANGELOG 1.3.2 notes "The PQ is still in Beta" and records a breaking key-format change for nested-model priority queues in the same release.
- Files: `rapyer/types/priority_queue.py`
- Impact: Less battle-tested than other special field types (`RedisSet`, `RedisDict`); nested-model usage previously silently produced a fresh/empty queue after a key-format change.
- Fix approach: Treat as lower-priority/riskier when building new features (e.g., cascade) on top of it; add explicit regression tests for nested usage before relying on it structurally.

## Known Bugs (history of fragility, from CHANGELOG)

**Nested special-field handling is a recurring source of bugs:**
- Symptoms (fixed in 1.3.3, but indicative of an ongoing risk area): `asave`, `aduplicate`, `ainsert`, batch creation, and `aget_or_create` previously only persisted special fields declared directly on the top-level model — special fields nested inside a sub-model were silently dropped.
- Files: `rapyer/base.py` (`_iter_special_fields` at `rapyer/base.py:763-777`, `queue_special_loads_in_pipeline` at `rapyer/base.py:656-667`)
- Trigger: Any new special-field-touching action (save/delete/duplicate/TTL) that iterates only top-level fields instead of recursing through `_iter_special_fields`.
- Workaround: None needed post-fix, but any new cascade/TTL logic must route through the same recursive helpers rather than re-implementing top-level-only iteration.

**Root-model resolution is the single point that keeps TTL correct for nested/linked models:**
- Symptoms (fixed in 1.3.3): actions triggered through a nested model or special field previously refreshed TTL on the wrong key because they didn't walk back to the aggregate root.
- Files: `rapyer/actions.py:89-101` (`resolve_root_model`)
- Trigger: Bypassing `resolve_root_model` when registering a new action target (e.g., a hand-rolled cascade action) would reintroduce the same class of bug for any model reachable via `_base_model_link`.
- Workaround: New relational/cascade code must call `register_action_target`/`resolve_root_model`, not touch `Meta.ttl`/`EXPIRE` directly.

**fakeredis vs real Redis behavioral divergence:**
- Symptoms (fixed in 1.3.3): `afind`/`afind_one` raised `IndexError` under fakeredis for missing keys because `JSON.MGET` returns `[]` per missing slot under fakeredis vs `None` under real Redis; `build_models_from_dumps` only guarded against `None`.
- Files: `rapyer/base.py` (missing-key guards near `aget`/`afind`, e.g. `rapyer/base.py:594-599`)
- Trigger: Any new pipeline-based load path that adds its own missing-key check instead of reusing the existing guard risks reintroducing this divergence, since fakeredis is the primary CI/unit-test backend for large parts of the suite.
- Workaround: Prefer the shared guard pattern already used in `aget`/`afind` for any new bulk-load code (relevant to eager-loading FK targets).

**`adelete_many` silently under-reports actual deletions:**
- Symptoms: `DeleteResult.models_deleted` reflects the number of *targeted* keys/models, not the number actually removed from Redis; deleting an already-missing key or a "stale" model (whose key was deleted out-of-band) returns `models_deleted=1, keys_deleted=0` without any error or warning.
- Files: `rapyer/base.py:910-970` (`adelete_many`), tests documenting the behavior: `tests/integration/functioninality/test_model_adelete_many.py:182-208`, `tests/integration/functioninality/test_rapyer_adelete_many.py:107-123`
- Trigger: Deleting keys/models that don't exist in Redis.
- Workaround: None — this is accepted/tested current behavior ("silent_skip"), but it means a future cascade-delete feature built on top of `adelete_many` would also silently succeed even if child/related keys were already gone, masking partial-cascade failures.

**fakeredis's JSON.GET does not emulate WRONGTYPE:**
- Symptoms: fakeredis 2.34.1 returns `"[]"` from `JSON.GET` against a plain-string (non-JSON) key instead of raising a WRONGTYPE error the way real Redis Stack does.
- Files: `rapyer/scripts/lua/cascade/library.lua::read_reference_paths` (the `redis.pcall('JSON.GET', ...)` WRONGTYPE guard).
- Trigger: Writing a fakeredis-only regression test for any code path that guards against a `JSON.GET` WRONGTYPE error -- the guard is untestable under fakeredis.
- Workaround: Regression coverage for `JSON.GET` WRONGTYPE handling must live in `tests/integration/foreign_keys/` against `real_redis_client`, never `tests/unit/cascade/` against `fake_redis_client` alone.

**TTL cascade traversal is real-Redis-7+-only (Redis Functions):**
- Symptoms: The cascade is a Redis Functions library (`FUNCTION LOAD` + `FCALL`), which fakeredis does not implement. On fakeredis the cascade edge-walk is disabled; `refresh_ttl`/`aset_ttl` fall back to a plain `EXPIRE` over the root's own main + special keys only (no traversal).
- Files: `rapyer/scripts/lua/cascade/library.lua`, `rapyer/scripts/registry.py` (`register_cascade_function`/`run_fcall`/`arun_fcall`), `rapyer/base.py` (`refresh_ttl`/`aset_ttl` `Meta.is_fake_redis` branch), `rapyer/init.py` (loads the function only on real Redis).
- Trigger: Any cascade-traversal assertion under fakeredis. `aset_ttl(cascade=True)` on fakeredis silently returns `CascadeResult(0, 0)` without following edges -- a divergence a fakeredis-only test cannot catch.
- Workaround: Cascade correctness is covered by `tests/integration/foreign_keys/` against `real_redis_client` (Redis-7+-gated via `requires_redis_functions`) only; non-cascade `Meta.ttl`/`refresh_ttl` stays dual-backend.

**Redis Functions are registered server-GLOBAL (not per-DB):**
- Symptoms: A loaded function persists across `SELECT`/`FLUSHDB` and is visible to every connection on the server; two rapyer processes with different model sets (e.g. CI workers) share one function namespace.
- Files: `rapyer/cascade/planner.py::cascade_names` (plan-hashed library + function names), `rapyer/scripts/registry.py::register_cascade_function` (`FUNCTION LOAD ... REPLACE`).
- Trigger: Concurrent processes/CI workers with differing baked plans could clobber each other's function under a shared name.
- Workaround: Both the library AND the registered function name carry the plan hash, so differing plans coexist under distinct names and identical plans are idempotent under `REPLACE`. Test fixtures must (re)register the function in setup; a `REDIS_DB` flush does not clear it.

## Security Considerations

**CI security scanners are informational, not blocking, for most checks:**
- Risk: `bandit.yml` runs with `exit_zero: true` (never fails the job) and globally skips `B101` (assert-used); `semgrep.yml` runs `semgrep ci --config=auto` with `continue-on-error: true`; `codeql.yml` uploads SARIF to the Security tab but does not appear to gate PR merges in `ci.yml`. Only `security.yml`'s `pip-audit --strict` (dependency vulnerabilities) and `gitleaks-action` (secret scanning) can fail a workflow run.
- Files: `.github/workflows/bandit.yml`, `.github/workflows/semgrep.yml`, `.github/workflows/codeql.yml`, `.github/workflows/security.yml`
- Current mitigation: Findings still surface in the GitHub Security tab for manual triage; `pip-audit` and `gitleaks` do enforce hard failures.
- Recommendations: If bandit/semgrep/CodeQL findings should block merges (e.g., once cascade/delete code touches more Lua/eval paths), wire their results into required status checks instead of leaving them `exit_zero`/`continue-on-error`.

**Pickle-based deserialization for non-JSON-serializable fields:**
- Risk: Fields that aren't natively Redis/JSON serializable are pickled and base64-encoded on write, then `pickle.loads`-ed on read by default (`prefer_normal_json_dump=False` is the default in `RedisConfig`). `pickle.loads` on data read from Redis is a classic unsafe-deserialization vector if the Redis instance is ever shared, exposed, or writable by an untrusted party.
- Files: `rapyer/base.py:99-150` (`make_pickle_field_serializer`, `pickle_field_validator`), `rapyer/config.py:53` (`prefer_normal_json_dump` flag)
- Current mitigation: `SafeLoad[T]` catches deserialization exceptions and nulls the field instead of crashing (`rapyer/base.py:139-145`), but this does not prevent code execution during unpickling of a maliciously crafted payload — it only prevents the *exception* from propagating.
- Recommendations: Document that Redis must be treated as a trusted store (not exposed to untrusted writers); consider defaulting `prefer_normal_json_dump=True` for JSON-serializable fields, or offering a stricter opt-out of pickle entirely for security-sensitive deployments.

**No built-in TLS/auth configuration surface beyond the connection URL:**
- Risk: `RedisConfig.redis` defaults to `redis://localhost:6379/0` with no dedicated fields for TLS or credential rotation; auth/TLS must be embedded in the URL or configured on the externally-constructed `Redis` client passed in.
- Files: `rapyer/config.py:21-43`
- Current mitigation: Users can pass a fully configured `redis.asyncio.Redis` client, so this is a documentation/ergonomics gap rather than a blocking limitation.
- Recommendations: None required functionally; note in docs when adding config-related features (e.g., TTL config) that connection security is entirely delegated to the caller-supplied client.

## Performance Bottlenecks

**N+1 round trips on ForeignKey resolution:**
- Problem: `ForeignKey.afetch()` performs exactly one `target_cls.aget(self._target_key)` per call; there is no batch/eager-fetch API across a list of parent models or a chain of references.
- Files: `rapyer/types/foreign_key.py:60-73`
- Cause: Each reference is resolved independently and lazily; CHANGELOG 1.3.2 explicitly defers "eager fetch with depth control" to a follow-up release, and it remains unimplemented as of 1.3.3.
- Improvement path: Add a batched-resolve entry point (e.g., `afetch_many`/`with_related`) that groups targets by model class and issues one `JSON.MGET`-based pipeline per class (reusing `execute_load_pipeline` in `rapyer/utils/redis.py:32-`), instead of one `aget` per instance. Relevant when adding cascade/eager-load features.

**Non-atomic multi-batch deletes:**
- Problem: `adelete_many` splits large delete sets into pipelines capped by `Meta.max_delete_per_transaction` (default 1000); each batch is its own `pipe.execute()` transaction (`delete_in_batches`), so the overall delete across many batches is not atomic — a mid-run failure leaves earlier batches committed and later ones not attempted.
- Files: `rapyer/base.py:929-970`, `rapyer/config.py:57` (`max_delete_per_transaction`)
- Cause: Trade-off to avoid one giant Redis transaction/pipeline for very large delete sets.
- Improvement path: If cascade deletes are added, decide explicitly whether cascades should share the same non-atomic batching (fast, but can leave orphaned children on partial failure) or be scoped so cascade targets fit inside a single transaction/pipeline per aggregate root.

**`afind_keys()` falls back to blocking `KEYS` when unbounded:**
- Problem: `afind_keys(max_results=None)` calls `cls.Meta.redis.keys(pattern)`, which is a known Redis anti-pattern (`O(N)` full keyspace scan, blocks the Redis event loop) for large deployments. Only the bounded path uses the non-blocking `SCAN`-based `scan_keys` helper.
- Files: `rapyer/base.py:742-750`, `rapyer/utils/redis.py:107-117`
- Cause: Convenience default for "return everything" without an explicit result cap.
- Improvement path: Default unbounded `afind_keys`/`afind` (used internally by `adelete_many`'s expression path too) to `SCAN` with no `count` limit instead of `KEYS`.

**Lua/pipeline recovery adds retry complexity on every pipeline exit:**
- Problem: Every `apipeline()` exit checks for `NoScriptError`, re-registers scripts, and replays only the `EVALSHA` commands in a fresh pipeline; this is necessary for correctness (Redis script cache can be flushed independently of app state) but is extra work on every pipeline execution path and a second failure (`noscript_on_retry`) raises `PersistentNoScriptError`.
- Files: `rapyer/base.py:1284-1332`, `rapyer/scripts/registry.py:107-135`
- Cause: Atomic actions (`aget_or_create`, special-field save/load) depend on server-side Lua scripts, which Redis can evict from its script cache (`SCRIPT FLUSH`, restart, failover).
- Improvement path: Acceptable as-is; any new cascade Lua scripts added for cross-key cascade operations must be registered through `rapyer/scripts/registry.py` so they participate in this same recovery path, not hand-rolled `EVAL` calls.

**`RedisDict.apop`/`apopitem` always bypass the active pipeline:**
- Problem: These two methods intentionally execute against the direct Redis client even inside `apipeline()`, because callers need the popped value synchronously — breaking the general assumption that operations inside `apipeline()` are batched/deferred.
- Files: noted in `CHANGELOG.md` (1.3.0 "Technical Improvements"); implementation in `rapyer/types/dct.py`
- Cause: Pop operations need an immediate return value that a queued pipeline command cannot provide before `execute()`.
- Improvement path: If adding cascade/atomic-multi-step features, audit for the same class of "needs an immediate value inside a pipeline" methods and document/test them explicitly, since they silently escape pipeline batching.

## Fragile Areas

**`AtomicRedisModel.__init_subclass__` metaprogramming:**
- Files: `rapyer/base.py:322-445`
- Why fragile: At class-definition time, this single method rewrites `__annotations__` into Redis-aware types, classifies fields as special/relational/FK-containing/redis-linked via a chain of `safe_issubclass` checks (order-dependent — e.g., `RelationalFieldType` is checked before the generic `BaseRedisType`/`AtomicRedisModel` containment check), and injects pickle serializers/validators. A change to check ordering or to `is_redis_field`/`replace_to_redis_types_in_annotation` can silently misclassify a field (e.g., a `ForeignKey`-containing nested model wrongly falling into `_contain_sf` instead of `_contain_fk`, or vice versa).
- Safe modification: Add new field-type detection as an additional, clearly-ordered branch with its own test in `tests/unit/test_init_rapyer.py` / `tests/models/`; never reorder existing `safe_issubclass` checks without full test-suite verification across `tests/integration/actions/redis_types/`.
- Test coverage: Covered by `tests/unit/test_init_rapyer.py` and the various `tests/integration/actions/redis_types/test_*.py` files, but there is no single test enumerating all classification branches together, so cross-branch regressions (e.g., a field that is both relational and special) are the likely blind spot.

**Class-level (not instance-level) relational target caching:**
- Files: `rapyer/types/foreign_key.py:24-25` (`_target_type_hint`, class attribute), `rapyer/types/relational.py:22-26` (`_relational_target`, class attribute)
- Why fragile: `ForeignKey`'s target type is stored on the *class*, not per instance. This only works because the metaclass generates a distinct per-field dynamic subclass for each differently-typed `ForeignKey[...]` field (per the `#247` TODO). If that per-field-subclass mechanism is ever changed or bypassed, two `ForeignKey` fields with different target types on the same or sibling models would clobber each other's `_relational_target`.
- Safe modification: Any refactor of relational-target resolution must preserve per-field type isolation (either via the current subclassing approach or by moving `_relational_target` to instance state).
- Test coverage: `tests/integration/actions/redis_types/test_foreign_key.py` (38 lines — fairly small for the amount of metaprogramming behind it).

**Dual-version action wrapping and re-installation across a class hierarchy:**
- Files: `rapyer/actions.py:335-392` (`install_action_for_meta`, `install_marked_action_methods`)
- Why fragile: `install_marked_action_methods` peels back only wrapper layers tagged with `ACTION_WRAPPER_SENTINEL` (i.e., wrappers it installed itself) while preserving other decorators like `marks_redis_updated`. A new decorator added around an action method that doesn't follow this sentinel convention, or is applied in the wrong order, will either be silently skipped during re-installation or double-wrapped.
- Safe modification: New action-bearing methods should use `@mark_actions(...)` as the outermost or otherwise well-understood layer, and any custom wrapper meant to survive re-installation must set `ACTION_WRAPPER_SENTINEL` and `__wrapped__` correctly (`functools.wraps`).
- Test coverage: `tests/unit/mark_actions/test_reinstall.py`, `tests/unit/test_action_groups.py` — reasonable coverage of the mechanism itself, but no coverage combining it with a future cascade decorator.

## Scaling Limits

**Delete fan-out batching:**
- Current capacity: `max_delete_per_transaction` defaults to 1000 keys per pipeline transaction (`rapyer/config.py:57`).
- Limit: A cascade-delete feature touching many related child keys per parent would need many sequential pipeline round trips (serial, no concurrency) once fan-out exceeds this batch size.
- Scaling path: Increase `max_delete_per_transaction`, or parallelize independent batches (e.g., `asyncio.gather` over batches against non-conflicting keys) if cascade delete becomes a hot path.

**Unbounded `afind`/index-based queries:**
- Current capacity: Bounded queries use RediSearch (`_search_keys_by_query`, `iter_filter_batches`) with cursoring; unbounded key enumeration without an index falls back to `KEYS` (see Performance section).
- Limit: Keyspaces with millions of keys will see `KEYS`-based calls block the Redis server for a noticeable duration.
- Scaling path: Route all unbounded enumeration through `SCAN`-based `scan_keys`/`iter_filter_batches` instead of `KEYS`.

## Dependencies at Risk

**fakeredis vs real Redis parity:**
- Risk: The test suite relies heavily on `fakeredis[lua,json]` for unit tests (see `tests/integration/conftest.py`, `is_fake_redis` flag in `rapyer/config.py:55`) while integration tests also run against a real Redis service matrix (redis 6.0–7.4 in `ci.yml`). Past bugs (missing-key `[]` vs `None`, see "Known Bugs") originated specifically from fakeredis/real-Redis behavioral divergence.
- Impact: New Lua-script-based features (e.g., cascade actions implemented as Lua) are the highest-risk category for this divergence, since fakeredis's Lua support is a reimplementation, not the real Redis scripting engine.
- Migration plan: None needed, but new atomic/Lua features should get explicit test coverage against `real_redis_client` fixtures, not fakeredis alone.

## Missing Critical Features (relevant to cascade actions / TTL config / table-like structure)

**No cascade behavior for save/delete/duplicate/TTL across relations:**
- Problem: `ForeignKey`/`Reference[T]` is a lazy, inline reference only. `adelete()`/`adelete_by_key()` delete exactly the keys of the model being deleted (`rapyer/base.py:845-863`, `_all_keys_for_key` at `rapyer/base.py:559-569`) and never traverse `_relational_field_names`/`_contain_fk` to reach referenced models. `aduplicate()` and TTL refresh similarly do not propagate to FK targets.
- Blocks: Any cascade-on-delete, cascade-on-save, or cascade-TTL-refresh semantics. This was explicitly called out and deferred in CHANGELOG 1.3.2: *"Cascade behavior (save / delete / duplicate / TTL) and eager fetch with depth control land in follow-up PRs."* — still true as of 1.3.3.
- Relevant hook points for implementation: `resolve_root_model`/`register_action_target` (`rapyer/actions.py:89-119`) already centralize "which model(s) does this action affect" — a cascade feature should extend target registration here rather than duplicating traversal logic in `adelete`/`asave`. Field classification sets `_relational_field_names` and `_contain_fk` (populated in `rapyer/base.py:367-398`) already identify which fields on a model need to be walked for cascade purposes.

**No per-field / per-relationship TTL configuration:**
- Problem: TTL is a single `int | None` on `RedisConfig` (`rapyer/config.py:45`), interpreted as a property of the aggregate root only (`resolve_root_model`, `rapyer/actions.py:89-101`). There is no way to give a referenced/child model a different TTL than its own `Meta.ttl`, and no concept of "TTL relative to parent" or "sliding vs. fixed TTL" beyond the existing `refresh_ttl: bool | ActionGroup` per-action-group toggle.
- Blocks: Fine-grained TTL policies (e.g., "children expire independently," "children inherit parent's remaining TTL," "cascade TTL refresh to related models on parent read").
- Additional gap: `init_rapyer(ttl=...)` overwrites **every** registered model's `Meta.ttl` uniformly (`rapyer/init.py:45-46`) — there is no per-model TTL override surface at init time; callers must mutate each model's `Meta.ttl` individually after calling `init_rapyer()`.

**No table-like relational integrity constructs:**
- Problem: No unique-constraint enforcement, no foreign-key existence validation at write/assign time (a `ForeignKey` can be constructed from an arbitrary string key that doesn't exist in Redis; `afetch()` only raises `KeyNotFound` when someone actually resolves it — `rapyer/types/foreign_key.py:60-73`), and no "on delete" policy vocabulary (RESTRICT / CASCADE / SET NULL) anywhere in the codebase (`grep -rn "on_delete\|CASCADE" rapyer/` returns nothing).
- Blocks: Any "table-like structure" feature that wants relational-database-style referential integrity guarantees; today rapyer is closer to a lazy pointer than a foreign-key constraint.

**No eager-loading / depth-limited fetch API:**
- Problem: See "N+1 on ForeignKey resolution" above — there is no `with_related(depth=N)`-style API for hydrating a graph of references in one or few round trips.
- Blocks: Efficient reads of object graphs; currently a caller must manually `await` `afetch()` per reference per instance.

## Test Coverage Gaps

**Coverage is informational, not a hard CI gate:**
- What's not tested (as a gate): `codecov.yml` sets `informational: true` and `target: auto` for both `project` and `patch` status checks — a PR that reduces coverage does not fail the coverage-specific check (though `lint`/`mypy`/`test` in `ci.yml` are still required).
- Files: `codecov.yml`, `.github/workflows/coverage.yml`
- Risk: Coverage regressions on new code (e.g., a hastily added cascade feature) would not block merge on coverage grounds alone.
- Priority: Medium — worth tightening before adding a large surface-area feature like cascade actions.

**No tests for cross-model cascade behavior:**
- What's not tested: There is no test file covering cascade delete/save/duplicate/TTL across `ForeignKey`/`Reference` relations (expected, since the feature doesn't exist yet). The closest existing test, `tests/integration/actions/two_model_delete.py` (`TwoModelDeleteBase`), explicitly asserts the *opposite*: deleting one model does not affect a second, unrelated model.
- Files: `tests/integration/actions/two_model_delete.py`, `tests/integration/actions/redis_types/test_foreign_key.py` (38 lines)
- Risk: Zero regression safety net for a new cascade feature; existing tests would need to be reconciled (they test "no cascade" as current correct behavior) before/while adding opt-in cascade semantics.
- Priority: High — write cascade-specific integration tests before/alongside implementation, and confirm `TwoModelDeleteBase`'s assumptions still hold for the non-cascading (default) configuration.

**Silent-skip delete semantics are tested but not flagged as a design risk:**
- What's not tested: There's no test asserting *warning/telemetry* behavior when `adelete_many` silently skips missing keys — only that the silent skip itself is the intended behavior (`test_adelete_many__missing_key_silent_skip`, `test_adelete_many__stale_model_silent_skip`).
- Files: `tests/integration/functioninality/test_model_adelete_many.py:182-208`, `tests/integration/functioninality/test_rapyer_adelete_many.py:107-123`
- Risk: If cascade delete is layered on top of `adelete_many`, a partially-failed cascade (some children already gone) would report success identically to a fully successful cascade.
- Priority: Medium — consider whether cascade delete needs a distinct result type that distinguishes "target already absent" from "target successfully removed by this call."

---

*Concerns audit: 2026-07-06*
