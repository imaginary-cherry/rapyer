# Coding Conventions

**Analysis Date:** 2026-02-05

## Naming Patterns

**Files:**
- Snake case for Python files: `base.py`, `conftest.py`, `test_operations.py`
- Type-specific modules grouped under directories: `types/string.py`, `types/integer.py`, `types/dct.py`
- Test files use `test_` prefix: `test_base_creation.py`, `test_redis_str_operations.py`

**Functions:**
- Async functions prefixed with `a`: `asave()`, `aload()`, `aget()`, `afind()`, `ainsert()`, `alock_from_key()`, `apipeline()`
- Regular functions use snake_case: `create_all_types()`, `make_pickle_field_serializer()`, `_collect_annotations_recursive()`
- Private/internal functions prefixed with underscore: `_context_var`, `_base_model_link`, `_field_name`

**Variables:**
- Class variables use UPPER_CASE with leading underscore: `_pk`, `_base_model_link`, `_failed_fields`, `_key_field_name`, `_safe_load_fields`, `_field_name`
- Instance variables use snake_case: `field_name`, `original_type`, `json_path`
- Private attributes use leading underscore: `_adapter`, `_base_model_link`
- Magic variables use double underscore both sides: `REDIS_DUMP_FLAG_NAME`, `FAILED_FIELDS_KEY`

**Types:**
- Classes use PascalCase: `RedisType`, `RedisStr`, `RedisInt`, `RedisList`, `RedisDict`, `AtomicRedisModel`, `RedisConfig`
- Type aliases use PascalCase: `Self`, `TypeAlias`

## Code Style

**Formatting:**
- Tool: Black (version ^25.9.0)
- Configuration in `pyproject.toml`
- Enforce with tox linting step: `tox -e lint`
- Max line length: Default (88 characters by Black standard)

**Linting:**
- Tool: None configured (bandit for security only)
- Bandit excludes test files with `exclude_dirs = ["tests"]`
- Bandit skips `B101` (assert_used) as valid in tests

**Type Checking:**
- Tool: mypy (version ^1.0.0)
- Config: `--follow-imports=skip --no-error-summary --disable-error-code=valid-type`
- Run via tox: `tox -e mypy`
- Focuses on `tests/models` directory

## Import Organization

**Order:**
1. Standard library (abc, asyncio, base64, contextlib, dataclasses, functools, json, logging, os, pickle, uuid, typing modules)
2. Third-party packages (pydantic, pydantic_core, redis, redis.asyncio, fakeredis, pytest, pytest_asyncio)
3. Local imports (rapyer modules: rapyer.base, rapyer.config, rapyer.context, rapyer.errors, rapyer.fields, rapyer.links, rapyer.scripts, rapyer.types, rapyer.typing_support, rapyer.utils)
4. Test-specific imports (tests.models, tests.assertions)

**Path Aliases:**
- No path aliases configured
- Absolute imports used throughout: `from rapyer.base import AtomicRedisModel`
- Standard type imports: `from typing import ClassVar, Any, get_origin, Optional, TypeVar, Generic`
- TYPE_CHECKING guard: `if TYPE_CHECKING:` for type-only imports

## Error Handling

**Patterns:**
- Custom exception hierarchy in `rapyer/errors/base.py`
- Base class: `RapyerError(Exception)` with docstring
- Specific exceptions inherit from `RapyerError`: `KeyNotFound`, `FindError`, `BadFilterError`, `RapyerModelDoesntExistError`, `UnsupportedIndexedFieldError`, `CantSerializeRedisValueError`, `ScriptsNotInitializedError`, `PersistentNoScriptError`
- Exceptions with custom `__init__` for additional context: `RapyerModelDoesntExistError(model_name: str)`
- Raise with context using `from e`: `raise CantSerializeRedisValueError() from e`
- Exception handling in pickle validators catches `Exception` broadly, logs warnings, returns None for SafeLoad fields

## Logging

**Framework:** Python standard logging module (`import logging`)

**Patterns:**
- Module-level logger created as: `logger = logging.getLogger("rapyer")`
- One logger per module (e.g., `rapyer/types/base.py`, `rapyer/types/lst.py`)
- Log levels used: `logger.warning()` for non-critical issues like SafeLoad deserialization failures
- Context logged: field names, error details
- Example: `logger.warning("SafeLoad: Failed to deserialize field '%s'", field)`

## Comments

**When to Comment:**
- Minimal comments; none required for clear code
- Only included when crucial for understanding (per project guidelines)
- Seen in base.py: `# Note: This should be overridden...`, `# Avoid infinite loops`, `# Skip object class`
- Inline comments explain complex logic or non-obvious behavior

**JSDoc/TSDoc:**
- Python docstrings used sparingly
- Docstrings appear primarily on classes and public helper functions
- Format: Triple-quoted strings on next line after definition
- Example in `rapyer/utils/fields.py`: Multi-line docstring with Args section

## Function Design

**Size:**
- Mostly compact, under 50 lines
- Async methods (`asave`, `aload`) follow pattern: setup, operation, return
- Helper functions extract complex logic: `make_pickle_field_serializer()` creates paired serializer/validator

**Parameters:**
- Type hints used throughout: `def sub_field_path(self, key: str) -> str`
- Optional parameters with defaults: `exclude_classes: type[BaseModel] = None`
- Union types using `|` syntax: `model_dump = self._adapter.dump_python(self, mode="json", context={...})`
- `*args, **kwargs` used in `__init__` methods for flexibility
- Unpacked TypeVar parameters: `Unpack[AtomicRedisModel]` for variadic function arguments

**Return Values:**
- Explicit return types: `-> Self`, `-> dict[str, FieldInfo]`, `-> bool`
- Async functions return awaitable objects
- Properties use `@property` decorator with type hints
- Validation methods return transformed values or raise exceptions

## Module Design

**Exports:**
- Explicit `__all__` in `rapyer/__init__.py`: `["AtomicRedisModel", "init_rapyer", "teardown_rapyer", ...]`
- Barrel files use `__all__` to control public API
- Private modules not exported

**Barrel Files:**
- `rapyer/__init__.py` re-exports main classes and functions
- Type modules like `rapyer/types/__init__.py` exist but minimal exports
- Test models in `tests/models/` organized by type category

---

*Convention analysis: 2026-02-05*
