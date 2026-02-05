# Testing Patterns

**Analysis Date:** 2026-02-05

## Test Framework

**Runner:**
- pytest (version >=8.4.2)
- Config: `pyproject.toml` (no separate pytest.ini)
- Supports assertion rewriting via: `pytest.register_assert_rewrite("tests.assertions")`

**Assertion Library:**
- pytest built-in assertions
- Direct equality/truthiness checks: `assert isinstance(..., RedisStr)`, `assert model.name == expected_value`

**Run Commands:**
```bash
pytest                              # Run all tests
pytest -v                           # Verbose output
pytest -s                           # Show print statements
tox -e py312                        # Run tests with specific Python/Redis/Pydantic combo
tox                                 # Run all environments (py310-313 x redis60-64 x pydantic211-212 + lint + mypy)
pytest --cov=rapyer                 # Generate coverage report
```

## Test File Organization

**Location:**
- Co-located with source: `tests/` directory mirrors structure of `rapyer/` source
- Separate directory structure: `tests/unit/`, `tests/integration/`, `tests/models/`

**Naming:**
- Test functions: `test_<feature>_<condition>_<assertion>` pattern
  - Examples: `test_redis_str_operations_sanity`, `test_model_creation_with_defaults__check_redis_type_inheritance_and_json_path_sanity`
  - Descriptive names replace docstrings
  - Double underscore separates logical units: `test_name__check_specific_behavior`
- Test modules: `test_<subject>.py`
  - Examples: `test_operations.py`, `test_initialization.py`, `test_base_creation.py`
- Conftest files: `conftest.py` at test level

**Structure:**
```
tests/
├── conftest.py                     # Decorators and global fixtures
├── models/                         # Shared test model definitions
│   ├── simple_types.py            # StrModel, IntModel, etc.
│   ├── collection_types.py        # ListModel, DictModel variants
│   ├── complex_types.py           # OuterModel, InnerModel
│   └── unit_types.py              # SimpleStringModel, SimpleIntModel (non-async)
├── unit/
│   ├── conftest.py                # fake_redis_client fixture
│   ├── models/
│   │   ├── test_base_creation.py
│   │   ├── test_nested_creation.py
│   │   └── test_model_dump.py
│   ├── types/
│   │   ├── simple_types/
│   │   │   ├── test_initialization.py
│   │   │   ├── test_operations.py
│   │   │   └── test_redis_float.py
│   │   ├── collection_types/
│   │   │   ├── test_initialization.py
│   │   │   ├── test_operations.py
│   │   │   └── test_redis_list_remove_range.py
│   │   └── complex_types/
│   │       ├── test_operations.py
│   │       └── test_initialization.py
│   └── pipeline/
│       ├── test_apipeline_response_error.py
│       └── test_pipeline_setattr_with_fakeredis.py
└── integration/
    ├── conftest.py                # redis_client fixture, model imports
    ├── models/
    ├── simple_types/
    ├── functioninality/
    │   └── conftest.py            # setup_fake_redis_for_models fixture
    └── pipeline/
```

## Test Structure

**Suite Organization:**
```python
@pytest.mark.parametrize(
    ["param1", "param2"],
    [
        [value1a, value2a],
        [value1b, value2b],
    ]
)
async def test_feature__check_behavior(param1, param2):
    # Arrange
    model = SimpleStringModel(name=param1)

    # Act
    result = model.name + param2

    # Assert
    assert result == expected
```

**Patterns:**
- **Setup (Arrange):** Create fixtures, initialize models, set up state
- **Execution (Act):** Call methods, perform operations
- **Verification (Assert):** Check state, values, types, properties
- Each block marked with comment: `# Arrange`, `# Act`, `# Assert`
- Parametrization: `@pytest.mark.parametrize()` with list of parameters and list of test cases
  - Parameter format: `[["param1_name", "param2_name"], [[case1_val1, case1_val2], [case2_val1, case2_val2]]]`

**Async Tests:**
- Marked with `@pytest.mark.asyncio` decorator
- Use `async def test_...` syntax
- Example:
```python
@pytest.mark.asyncio
async def test_model_creation_with_nested_base_model__check_atomic_base_inheritance_and_json_path_sanity():
    # Arrange & Act
    model = OuterModel()

    # Assert
    assert isinstance(model.middle_model, AtomicRedisModel)
```

## Mocking

**Framework:** unittest.mock via `from unittest.mock import AsyncMock, patch`

**Patterns:**
```python
# In conftest.py for integration tests
from unittest.mock import AsyncMock, patch

# Usage in test
with patch('module.function') as mock_func:
    mock_func.return_value = expected_value
```

**What to Mock:**
- Redis client for unit tests (use FakeRedis)
- External services
- AsyncMock for async functions

**What NOT to Mock:**
- Core model behavior
- Redis type conversions
- Serialization/deserialization logic

## Fixtures and Factories

**Test Data:**

FakeRedis fixture (unit tests):
```python
@pytest_asyncio.fixture
async def fake_redis_client():
    client = fake_aioredis.FakeRedis(decode_responses=True)
    await register_scripts(client, is_fakeredis=True)
    yield client
    await client.aclose()
```

Model fixture (integration tests):
```python
@pytest.fixture
def setup_fake_redis_for_models(fake_redis_client):
    original_clients = {}
    models = [StrModel, IntModel, IndexTestModel, PersonModel, AddressModel, AtomicRedisModel]
    for model in models:
        original_clients[model] = (model.Meta.redis, model.Meta.is_fake_redis)
        model.Meta.redis = fake_redis_client
        model.Meta.is_fake_redis = True
    yield
    for model, (original_redis, original_is_fake) in original_clients.items():
        model.Meta.redis = original_redis
        model.Meta.is_fake_redis = original_is_fake
```

**Location:**
- `tests/conftest.py`: Global decorators and utilities
- `tests/unit/conftest.py`: Unit test fixtures (fake_redis_client)
- `tests/integration/conftest.py`: Integration test fixtures (model imports, AsyncMock definitions)
- `tests/unit/functioninality/conftest.py`: Functional test fixtures (setup_fake_redis_for_models)
- `tests/models/`: Test model definitions (not fixtures, but reusable test classes)

## Coverage

**Requirements:** No target enforced in config

**View Coverage:**
```bash
pytest --cov=rapyer --cov-report=html --cov-report=term
```

**Configuration:** (in `pyproject.toml`)
```toml
[tool.coverage.run]
source = ["rapyer"]
omit = ["*/tests/*", "*/test_*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
]
```

## Test Types

**Unit Tests:**
- Location: `tests/unit/`
- Scope: Individual functions, methods, types in isolation
- Use FakeRedis for Redis operations
- Test initialization, operations, type casting
- Examples: `tests/unit/types/simple_types/test_operations.py`, `tests/unit/models/test_base_creation.py`
- Approach: Direct instantiation of models, method calls, assertion on results

**Integration Tests:**
- Location: `tests/integration/`
- Scope: Multiple components working together
- Use real Redis client or FakeRedis with full setup
- Test model persistence, retrieval, complex workflows
- Examples: `tests/integration/models/`, `tests/integration/functioninality/`
- Approach: Setup models, save/load, verify state persistence

**E2E Tests:**
- Framework: Not used (focus on unit and integration)
- Redis is treated as external system, tested via integration tests

## Common Patterns

**Async Testing:**
- Marked with `@pytest.mark.asyncio`
- pytest-asyncio provides async fixture support
- Async conftest fixtures use `@pytest_asyncio.fixture` with `async def`
- Example:
```python
@pytest_asyncio.fixture
async def fake_redis_client():
    client = fake_aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()
```

**Parametrized Testing:**
- Use `@pytest.mark.parametrize(["param_names"], [[case1_vals], [case2_vals]])`
- Parameter names as list of strings
- Test cases as list of lists (each case is a list of values)
- Example from test_operations.py:
```python
@pytest.mark.parametrize(
    "initial_value,new_value", [("hello", "world"), ("", "test"), ("old", "new")]
)
def test_redis_str_operations_sanity(initial_value, new_value):
    # Arrange
    model = SimpleStringModel(name=initial_value)

    # Act - Test assignment
    model.name = new_value

    # Assert
    assert isinstance(model.name, RedisStr)
```

**Error Testing:**
- Direct exception raising in code
- Test with pytest.raises context manager (if validation needed)
- Focus on correct behavior under valid conditions (not exhaustive error cases)

**Type Assertions:**
- `assert isinstance(value, ExpectedType)` for type checking
- `assert hasattr(obj, "attr_name")` for attribute presence
- `assert obj.attr == expected_value` for equality

**TTL Testing:**
- Custom decorators in `tests/conftest.py`: `@ttl_test_for(method)` and `@ttl_no_refresh_test_for(method)`
- Tracks which methods have TTL/refresh tests
- TTL value set during fixture: `REDUCED_TTL_SECONDS = 10`

---

*Testing analysis: 2026-02-05*
