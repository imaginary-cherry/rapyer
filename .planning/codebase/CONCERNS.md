# Codebase Concerns

**Analysis Date:** 2026-02-05

## Tech Debt

**Silent exception swallowing in initialization:**
- Issue: `init_rapyer()` silently catches `ResponseError` on index deletion and creation without logging
- Files: `rapyer/init.py:55-56, 59-61`
- Impact: Index creation failures can fail silently if `override_old_idx=False`, making debugging difficult. No indication that index setup failed
- Fix approach: Add explicit logging at WARN level for caught exceptions. Consider re-raising or returning status information

**Bare pass statements in error handlers:**
- Issue: `rapyer/init.py:56` catches ResponseError but silently passes without logging
- Files: `rapyer/init.py:55-56`
- Impact: Production errors can go unnoticed. Makes troubleshooting impossible when index operations fail
- Fix approach: Replace bare pass with proper exception logging and context preservation

**Silent object state loss in SafeLoad:**
- Issue: When field deserialization fails with `safe_load=True`, the field is set to None without logging which field failed or why
- Files: `rapyer/base.py:91-96`
- Impact: Silent data loss - users don't know which fields were corrupted or unserializable. Application logic may break silently
- Fix approach: Add field context to logging. Consider collecting failed field details for user introspection

**Global REDIS_MODELS registry mutation:**
- Issue: `REDIS_MODELS` list grows whenever a model class is defined (subclassed)
- Files: `rapyer/base.py:603, 292`
- Impact: Memory leak in long-running applications or test suites that dynamically create many model classes. Can cause issues with test isolation
- Fix approach: Add cleanup mechanism or use weak references. Document that model class definition has side effects

**Bare pass in script registry:**
- Issue: `rapyer/scripts/registry.py:88` silently catches NoScriptError with pass
- Files: `rapyer/scripts/registry.py:85-88`
- Impact: Script loading failure is hidden. Downstream calls to `get_script()` will fail with confusing errors about uninitialized scripts
- Fix approach: Add logging to surface script re-registration failures

## Known Bugs

**Index creation race condition:**
- Symptoms: Index creation may fail if multiple processes try to create the same index simultaneously
- Files: `rapyer/base.py:201-211`
- Trigger: Concurrent calls to `acreate_index()` on the same model from multiple processes/tasks
- Workaround: Coordinate index creation in a single initialization phase, don't call `acreate_index()` concurrently

**ResponseError swallowing in init_rapyer with override_old_idx=True:**
- Symptoms: Index deletion succeeds but index creation fails, but error is silently ignored if override_old_idx=False on second run
- Files: `rapyer/init.py:52-61`
- Trigger: Network issues during index operations, or Redis permissions issues
- Workaround: Manually delete indexes and retry initialization. Monitor Redis logs

## Security Considerations

**Pickle deserialization without validation:**
- Risk: Unpickling arbitrary data from Redis could allow code execution if Redis is compromised
- Files: `rapyer/base.py:73, 89`, `rapyer/types/base.py:4`
- Current mitigation: Only pickle serialized by the same Pydantic validators, relies on Redis being trusted
- Recommendations: Add type validation after unpickling. Consider replacing pickle with safer formats (msgpack, protobuf) for sensitive types

**Global exception suppression in pipeline:**
- Risk: `ignore_redis_error=True` flag silently suppresses all ResponseErrors, including permission/auth failures
- Files: `rapyer/base.py:537-552, 691-714`
- Current mitigation: Only affects operations explicitly opting in. Logged as warning
- Recommendations: Be more selective about which errors to ignore (network vs auth failures). Add metrics/monitoring for ignored errors

**No rate limiting on Redis.keys() calls:**
- Risk: `afind_keys()` uses KEYS pattern which can be slow on large datasets and block Redis
- Files: `rapyer/base.py:486`
- Current mitigation: Only used in afind() when no specific keys or expressions provided
- Recommendations: Migrate to SCAN command. Add warnings in docs about O(N) complexity

## Performance Bottlenecks

**REDIS_MODELS dict recreation on every aget() and afind() call:**
- Problem: Creating `{klass.__name__: klass for klass in REDIS_MODELS}` repeatedly on every query
- Files: `rapyer/base.py:607, 619`
- Cause: Dict comprehension happens on every call, should be cached
- Improvement path: Cache the mapping with invalidation on model registration. Use lazy-populated dict or WeakValueDictionary

**Synchronous field validation on every deserialization:**
- Problem: Complex field validation happens inline during model instantiation from Redis
- Files: `rapyer/base.py:388, 401`
- Cause: Pydantic validators run for all fields even if only a subset was modified
- Improvement path: Use selective field validation. Cache validation results for unchanged fields

**Pipeline logging copies entire command stack:**
- Problem: On NoScriptError, the full `commands_backup` list is created and logged for every retry
- Files: `rapyer/base.py:698`
- Cause: Inefficient debugging of pipeline retries
- Improvement path: Only log command count and types, not the full stack

## Fragile Areas

**Exception type coercion in apipeline:**
- Files: `rapyer/base.py:536-556`
- Why fragile: Catches both TypeError and KeyNotFound with identical behavior, but these indicate different failure modes. Adding new exception types requires modifying multiple handlers
- Safe modification: Create a custom exception hierarchy for pipeline initialization failures. Test each exception type separately
- Test coverage: Missing tests for specific exception scenarios during pipeline initialization

**Model class initialization with side effects:**
- Files: `rapyer/base.py:235-292`
- Why fragile: `__init_subclass__` modifies class annotations, adds serializers/validators, and mutates REDIS_MODELS. Any error mid-initialization leaves class in inconsistent state
- Safe modification: Validate all preconditions before mutation. Consider using factory function instead of metaclass
- Test coverage: No tests for partial initialization failures

**Context variable for pipeline in multi-task environment:**
- Files: `rapyer/context.py:7`, `rapyer/base.py:696`
- Why fragile: Uses `_context_var.set()` which returns a token. If token management fails, context is not reset. Not tested in concurrent scenarios
- Safe modification: Use try-finally in context managers. Test with asyncio task spawning
- Test coverage: Limited concurrent execution tests

**pickle field serialization with mode preference:**
- Files: `rapyer/base.py:62-102`
- Why fragile: Complex conditional logic based on `can_json`, `should_serialize_redis`, and `prefer_normal_json_dump`. Easy to get serialization/deserialization mismatch
- Safe modification: Create separate serializer paths. Test all combinations of flags
- Test coverage: Needs comprehensive coverage of all flag combinations

## Scaling Limits

**Redis key pattern matching with KEYS:**
- Current capacity: Works fine up to millions of keys, but O(N) complexity
- Limit: Performance degrades significantly with 10M+ keys per model
- Scaling path: Replace `KEYS()` with `SCAN()` implementation. Add pagination support to afind_keys

**Global REDIS_MODELS registry memory:**
- Current capacity: No limit on number of registered model classes
- Limit: Each model class adds overhead. Memory leak in applications that define 100+ model classes dynamically
- Scaling path: Implement model class deregistration. Use weak references for registered classes

**Single Redis connection per model:**
- Current capacity: Default pool is 20 connections
- Limit: High concurrency applications may exhaust connections
- Scaling path: Make connection pool size configurable. Support connection sharing across models

**Pipeline transaction size:**
- Current capacity: Limited by Redis pipeline memory
- Limit: Batches > 1M commands may cause issues
- Scaling path: Add automatic batching with chunking. Warn on large pipelines

## Dependencies at Risk

**Pydantic version constraint:**
- Risk: Pinned to <2.13.0, but >=2.11.0. Minor version changes to Pydantic can break field serialization
- Files: `pyproject.toml:51`
- Impact: Validator and serializer behavior sensitive to Pydantic version
- Migration plan: Test against Pydantic 2.13+. Consider loosening constraints after testing

**Redis library version constraint:**
- Risk: Pinned to <7.1.0. Version 7.x may have breaking changes in command syntax or pipeline behavior
- Files: `pyproject.toml:50`
- Impact: Future Redis upgrades require revalidation
- Migration plan: Monitor Redis-py releases. Create test suite for Redis 7.x compatibility

**FakeRedis Lua script compatibility:**
- Risk: Uses separate Lua scripts for FakeRedis vs real Redis, but scripts may drift over time
- Files: `rapyer/scripts/loader.py`, `rapyer/scripts/constants.py`
- Impact: Test suite may not catch real Redis failures if FakeRedis scripts diverge
- Migration plan: Unify script paths. Add integration tests against actual Redis in CI

## Missing Critical Features

**No built-in data migration system:**
- Problem: Changing model field types requires manual migration. No schema versioning or migration tracking
- Blocks: Data model evolution, version upgrades
- Workaround: Manual scripts to dump/reload data with field transformations

**No automatic index optimization:**
- Problem: Indexes are created statically at initialization. Can't rebuild or optimize without downtime
- Blocks: Performance tuning, index strategy changes
- Workaround: Manual index management via Redis CLI

**No transaction rollback or partial failure recovery:**
- Problem: Pipeline failures can leave partial writes in Redis. No way to rollback
- Blocks: ACID guarantees, complex multi-model operations
- Workaround: Manual cleanup or re-initialization from source of truth

## Test Coverage Gaps

**Pipeline context variable reset on exception:**
- What's not tested: `_context_var.reset()` is not called if exception occurs before line 697 in apipeline
- Files: `rapyer/base.py:689-737`
- Risk: Context leak could affect subsequent operations in same task
- Priority: **High** - affects correctness in error paths

**Concurrent apipeline calls in same task:**
- What's not tested: Behavior when nested/concurrent pipelines are used within same asyncio task
- Files: `rapyer/context.py`, `rapyer/base.py:536-556`
- Risk: Second pipeline context would overwrite first, causing commands to target wrong pipeline
- Priority: **High** - common error scenario

**SafeLoad field recovery and inspection:**
- What's not tested: Ability to detect and list which fields failed deserialization, or retry specific fields
- Files: `rapyer/base.py:117-118, 387-390`
- Risk: Applications can't diagnose data corruption
- Priority: **Medium** - affects debugging

**Index creation error recovery:**
- What's not tested: Behavior when index fields are invalid or exceed Redis limits
- Files: `rapyer/init.py:50-61`
- Risk: Index creation silently fails, model works but queries won't use indexes
- Priority: **Medium** - affects query performance

**Pickle deserialization with corrupted data:**
- What's not tested: Handling of partially corrupted pickle data, or pickle from different Python versions
- Files: `rapyer/base.py:86-97`
- Risk: Deserialization errors can crash application
- Priority: **Medium** - robustness against corrupt state

**Global REDIS_MODELS state isolation in tests:**
- What's not tested: REDIS_MODELS list is not cleared between tests, causing cross-test contamination
- Files: `rapyer/base.py:603, 292`
- Risk: Test order dependency, model name collisions in parallel tests
- Priority: **High** - affects test reliability

---

*Concerns audit: 2026-02-05*
