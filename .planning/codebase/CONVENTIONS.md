# Coding Conventions

**Analysis Date:** 2026-07-06

## Naming Patterns

**Files:**
- Snake_case module names matching their concept: `rapyer/base.py`, `rapyer/config.py`, `rapyer/types/foreign_key.py`, `rapyer/errors/delete.py`.
- Error modules split by domain under `rapyer/errors/`: `base.py` (generic/shared errors), `delete.py`, `find.py`. New error categories get their own module rather than being appended to `base.py`.
- Type implementations live one-per-concept under `rapyer/types/`: `dct.py` (dict), `lst.py` (list), `byte.py`, `integer.py`, `float.py`, `string.py`, `datetime.py`, `redis_set.py`, `priority_queue.py`, `foreign_key.py`, `relational.py`, `special.py`, `generic.py`, `convert.py`, `base.py`.

**Functions — async I/O prefix convention (critical):**
- Every method or module-level function that performs a Redis round trip is prefixed with `a`: `asave`, `aget`, `aload`, `afind`, `afind_one`, `afind_keys`, `ainsert`, `aupdate`, `adelete`, `adelete_many`, `adelete_by_key`, `aexists`, `aget_or_create`, `aduplicate`, `aduplicate_many`, `aset_ttl`, `aappend`, `aextend`, `aadd`, `aadd_many`, `aremove`, `apop`, `apopitem`, `aclear`, `alock`, `alock_from_key`, `apipeline`.
- Sync methods that only mutate the local Python mirror (no `a` prefix) mirror native container APIs: `RedisDict.update`, `RedisList.append`, `RedisSet.discard` — these behave like their builtin counterparts but queue a write when inside `async with rapyer.apipeline()`.
- Private/internal helpers use a single leading underscore: `_resolve_key`, `_all_keys_for_key`, `_iter_special_fields`, `_ttl_keys`, `_search_keys_by_query`. These are excluded from the public API and from the action-coverage matrix (see `tests/action_groups.py`, `PRIVATE_METHODS` / `PRIVATE_INHERITED_METHODS`).
- When adding a new Redis-touching method, follow the `a`-prefix convention without exception — the test suite's coverage machinery (`tests/conftest.py`, `_collect_methods`) discovers "actions" by scanning for async callables, and non-conforming names will be silently excluded from coverage enforcement.

**Types:**
- Redis-backed field types are named `Redis<Concept>`: `RedisStr`, `RedisInt`, `RedisFloat`, `RedisBytes`, `RedisDict`, `RedisList`, `RedisSet`, `RedisDatetime`, `RedisDatetimeTimestamp`, `RedisPriorityQueue`. Base classes: `BaseRedisType`, `RedisType` (`rapyer/types/base.py`).
- Model base class: `AtomicRedisModel` (`rapyer/base.py`).
- Exceptions end in `Error`, all inherit from `RapyerError` (`rapyer/errors/base.py`): `KeyNotFound`, `CorruptedModelError`, `RapyerModelDoesntExistError`, `MissingParameterError`, `UnsupportedArgumentValueError`, `UpdateAtomicModelError`, `InvalidRefreshTtlError`, `DuplicateModelNameError`, `RapyerSerializationError`, `NotResolvedError`. Domain-specific subclasses live in their own module (`FindError`, `BadFilterError`, `UnsupportedIndexedFieldError` in `rapyer/errors/find.py`; `BadDeleteActionError` in `rapyer/errors/delete.py`).
- Enums use `enum.Flag` for composable bitmask categories (`ActionGroup` in `rapyer/actions.py`: `READ`, `FETCH`, `CREATE`, `UPDATE`, `APPEND`, `DELETE`, `ERASE`, `ARITHMETIC`) and plain `enum.Enum` for closed sets (`MarkVersion`, `TargetSource`).

**Variables:**
- Module-level constants are `UPPER_SNAKE_CASE`: `ACTION_GROUPS_ATTR`, `MARK_ACTION_PARAMS_ATTR`, `REDIS_MODELS`, `FAILED_FIELDS_KEY`, `REDIS_DUMP_FLAG_NAME`, `DEFAULT_CONNECTION`.
- Class-private caches/registries use a single leading underscore even at module scope: `_context_pipe` (`rapyer/context.py`), `_action_context` (`rapyer/actions.py`).

## Code Style

**Formatting:**
- `black` (dev dependency, `pyproject.toml` `[dependency-groups] dev`) enforces formatting; no `[tool.black]` overrides are present, so defaults apply (88-char target line length, double quotes). CI (`lint` job in `.github/workflows/ci.yml`) runs `black --check --diff .`.
- `tox -e lint` also runs `black --check --diff .` as an alternate entry point.

**Linting:**
- `ruff` is scoped narrowly via `[tool.ruff.lint]` in `pyproject.toml`: `select = ["I", "F401"]` — only import-sort (`I`) and unused-import (`F401`) rules are enabled. Ruff is not used as a general-purpose linter here.
- `[tool.ruff.lint.isort] combine-as-imports = true`.
- CI runs `ruff check --diff .` in the same `lint` job as black.
- `bandit` security scanning is configured (`[tool.bandit]`): excludes `tests/`, skips `B101` (assert-used, valid in test files). Runs via `.github/workflows/bandit.yml`.
- CodeQL and Semgrep also run in CI (`.github/workflows/codeql.yml`, `.github/workflows/semgrep.yml`) but do not add project-specific style constraints beyond what's captured here.

**Type checking:**
- `mypy` runs via `tox -e mypy`: `mypy --follow-imports=skip --no-error-summary --disable-error-code=valid-type tests/models`. It only type-checks `tests/models` (the shared test model fixtures), not the `rapyer/` package itself — this validates that user-facing model definitions type-check cleanly against the installed `rapyer`+`pydantic`+`redis` combination in the matrix, rather than checking internal implementation types.
- Matrix-tested across Python 3.10–3.13 in CI (`mypy` job in `ci.yml`).

**Docstrings — project style guide (`~/.claude/rules/python-style.md`), apply going forward:**
- Prefer a self-explanatory function/method name over a docstring. If a name alone doesn't convey purpose, rename first.
- Only add a docstring when the name truly cannot convey purpose; never add one to a function that currently has none just for documentation's sake.
- When a docstring is warranted, keep it short, describe purpose (not implementation), and format as:
  ```python
  """
  desc
  """
  ```
- The existing codebase mixes one-line docstrings (`"""Raised when a key is not found in Redis."""`) and longer prose docstrings with `- backtick-bulleted` explanations (`ActionGroup`, `TargetSource` in `rapyer/actions.py`); inline comments (`#`) are used liberally to explain *why*, especially around subtle pipeline/TTL/coverage behavior — follow that same "comment the non-obvious reasoning" style for new code.

## Import Organization

**Order (enforced by `ruff`'s isort rule `I`):**
1. Standard library (`base64`, `contextlib`, `functools`, `json`, `logging`, `pickle`, `uuid`, `enum`, `inspect`, ...)
2. Third-party (`pydantic`, `redis`, `pytest`, `fakeredis`, ...)
3. First-party `rapyer.*` absolute imports
4. Test-only files additionally import `tests.*` absolute imports (never relative imports)

- All imports are absolute (`from rapyer.errors import ...`, `from tests.models.simple_types import ...`) — no relative imports (`from .errors import`) appear anywhere in `rapyer/` or `tests/`.
- Multi-symbol imports from one module are wrapped in parentheses, one symbol per line, alphabetically sorted (see `rapyer/base.py` top-of-file imports, and every test file with more than 2–3 imported names).
- `combine-as-imports = true` — `import x as y` combined with other names from the same module goes in a single import statement.
- `TYPE_CHECKING`-guarded imports are used to avoid circular imports where a type is only needed for annotations (`rapyer/actions.py`, `rapyer/utils/redis.py`, `rapyer/config.py` all guard `AtomicRedisModel`/`RedisConfig` imports behind `if TYPE_CHECKING:` and reference the type as a string literal, e.g. `"AtomicRedisModel"`).
- `from __future__ import annotations` is used in modules with heavy forward-reference/circular-import needs: `rapyer/actions.py`, `rapyer/config.py`, `rapyer/result.py`. Not used uniformly across the package — apply it only when postponed evaluation of annotations is needed to break a cycle.
- Python 3.10 compatibility shim pattern: `rapyer/typing_support.py` re-exports `Self`/`Unpack` from `typing`, falling back to `typing_extensions` with `# pragma: no cover` on the except branch. Use `from rapyer.typing_support import Self, Unpack` instead of importing directly from `typing` when these symbols are needed, to keep 3.10 support.

## Error Handling

**Hierarchy:**
- Every exception raised by `rapyer` inherits (directly or transitively) from `RapyerError` (`rapyer/errors/base.py`), which inherits from `Exception`. This lets consumers catch all library errors with a single `except RapyerError:`.
- Domain errors subclass a more specific base where one exists: `BadFilterError`, `UnsupportedIndexedFieldError` both extend `FindError` (itself a `RapyerError`) — see `rapyer/errors/find.py`.
- Errors that need context carry it as constructor args stored on `self`, not via message-string parsing: `RapyerModelDoesntExistError.__init__(self, model_name: str, *args)` and `DuplicateModelNameError.__init__(self, model_name: str, *args)` both call `super().__init__(*args)` then set `self.model_name = model_name`.
- Plain stdlib exceptions (`RuntimeError`, `TypeError`, `AttributeError`, `NameError`, `KeyError`) are used deliberately for programmer-error / protocol-violation cases that aren't really "Redis ORM domain errors" — e.g. `raise RuntimeError("Can only duplicate from top level model")` (`rapyer/base.py:500`), `ForeignKey.__getattr__` raising plain `AttributeError` (`rapyer/types/foreign_key.py:90`), `RedisDict.popitem` raising plain `KeyError` to match native `dict.popitem()` semantics (`rapyer/types/dct.py:157`). Match the semantics of the operation you're replacing (native dict/list/set behavior) rather than always reaching for a `RapyerError` subclass.
- Exception chaining with `raise ... from e` is used whenever an error is caught and re-raised as a different type, to preserve the original traceback: `raise CantSerializeRedisValueError() from e` (`rapyer/base.py:145`, `rapyer/types/generic.py:80`).
- Deprecation shim pattern (`rapyer/errors/__init__.py`): a module-level `__getattr__(name)` intercepts access to a renamed symbol, emits `warnings.warn(..., DeprecationWarning, stacklevel=2)`, and returns the new symbol; any other unknown name re-raises `AttributeError(f"module {__name__!r} has no attribute {name!r}")`. Marked with a `# TODO - we should remove this in the 1.4.0` comment — follow this pattern (module `__getattr__` + `DeprecationWarning` + removal-version TODO) for any future renames that need a compatibility window.

**Validation errors:**
- Pydantic `field_validator`/`model_validator` are used for config- and field-level validation, raising domain errors from inside validators rather than letting `pydantic.ValidationError` leak for domain-specific invariants: `RedisConfig._no_delete_in_refresh_ttl` raises `InvalidRefreshTtlError` when `refresh_ttl` includes `ActionGroup.DELETE` (`rapyer/config.py:70-80`).

## Logging

**Framework:** stdlib `logging`, one logger per module via `logging.getLogger("rapyer")` (`rapyer/base.py:104`) — not `__name__`-based per-module loggers; the whole package logs under the `"rapyer"` namespace.

**Patterns:**
- `logger.warning(...)` is used for recoverable/expected failure paths that the caller opted into (e.g. `SafeLoad` swallowing a deserialization failure): `logger.warning("SafeLoad: Failed to deserialize field '%s'", field)` (`rapyer/base.py:141`) — uses `%s`-style lazy formatting, not f-strings, for log calls.

## Async Patterns

- The library is asyncio-first: virtually all public I/O is `async def`, returning `Self`/`list[Self]`/`Optional[Self]` typed with `rapyer.typing_support.Self`.
- Pipeline-awareness is implemented via `contextvars.ContextVar` (`_context_pipe` in `rapyer/context.py`, `_action_context` in `rapyer/actions.py`) rather than passing a pipeline object through every call — this lets `async with rapyer.apipeline():` transparently batch writes issued by nested `a*` calls without changing their call signatures.
- `mark_actions(...)` / `install_marked_action_methods` decorator pattern (`rapyer/actions.py`) tags methods with an `ActionGroup` bitmask (`_action_groups` attribute) at class-definition time, driving both runtime TTL-refresh behavior and the test-suite's action-coverage enforcement — new Redis-touching methods must be decorated so they participate in both.
- Async context managers are used for locking (`alock`, `alock_from_key`, `acquire_lock` in `rapyer/utils/redis.py`) and pipelining (`apipeline`), both returning `AbstractAsyncContextManager`.

## Function Design

**Size:** Public API methods on `AtomicRedisModel` (`rapyer/base.py`) run 10–60 lines; the file itself is large (1331 lines) because it's the single hub for the model base class, but individual methods stay focused on one Redis operation each.

**Parameters:**
- Class methods that accept "a key or a model instance" normalize via a private resolver first: `cls._resolve_key(key: str | Self) -> str` (`rapyer/base.py:573`), called from `aget`, `aexists`, etc. Follow this normalize-then-branch pattern instead of duplicating `isinstance` checks in every public method.
- Variadic model arguments use `*models: Unpack[Self]` (`ainsert`) / `*args` for filter expressions (`afind`) rather than accepting a list, matching Redis pipeline call ergonomics.
- Optional/tunable behavior is passed as keyword-only-by-convention arguments with defaults (`max_results: Optional[int] = None`, `can_use_pipeline: bool = False`).

**Return Values:**
- Bulk find/insert operations return dedicated result dataclasses/models rather than tuples: `DeleteResult`, `GetOrCreateResult`, `GetOrCreateStatus`, `RapyerDeleteResult` (`rapyer/result.py`), all re-exported from the top-level package.

## Module Design

**Exports (`rapyer/__init__.py`):**
- The public API is an explicit `__all__` list re-exporting from internal modules: `AtomicRedisModel`, `init_rapyer`, `teardown_rapyer`, `aexists`, `aget`, `aget_or_create`, `afind`, `afind_one`, `find_redis_models`, `ainsert`, `adelete_many`, `alock_from_key`, `apipeline`, plus the result types (`DeleteResult`, `GetOrCreateResult`, `GetOrCreateStatus`, `RapyerDeleteResult`).
- Internal-only helpers imported for side effects are aliased with a leading underscore to signal "not part of the public surface": `resolve_forward_refs as _resolve_forward_refs`.
- Forward-reference resolution is done explicitly at import time (`_resolve_forward_refs()` called once at the bottom of `rapyer/__init__.py`) because `rapyer.result` types reference `AtomicRedisModel` before it's fully defined — a workaround for a circular-import-shaped problem; new modules with the same shape should follow this "define, import, then resolve" sequencing rather than restructuring imports.
- `rapyer/errors/__init__.py` re-exports every exception from its submodules (`base`, `delete`, `find`) into one flat namespace with an explicit `__all__`, so consumers only ever need `from rapyer.errors import X`.
- Submodules (`rapyer/types/`, `rapyer/fields/`, `rapyer/utils/`, `rapyer/scripts/`) each have an `__init__.py`; `rapyer/types/__init__.py` and `rapyer/types/init.py` register/aggregate all `BaseRedisType` subclasses (`ALL_TYPES`) so `RedisConfig.redis_type` has a default mapping without hand-enumeration elsewhere.
- Lua scripts are shipped as package data (`rapyer/scripts/lua/**/*.lua`, packaged via `[tool.hatch.build.targets.wheel] include = ["rapyer/**/*.lua"]`) and loaded/registered at runtime via `rapyer/scripts/loader.py` and `rapyer/scripts/registry.py` — server-side atomic operations (e.g. `aget_or_create`) are implemented as Lua, not Python, and referenced by name constants in `rapyer/scripts/constants.py` (e.g. `ATOMIC_GET_OR_CREATE_SCRIPT_NAME`).

---

*Convention analysis: 2026-07-06*
