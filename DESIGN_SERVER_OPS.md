# Server-Side Operations Design

## Overview

This feature enables executing complex operations entirely on the Redis server without round-tripping data through Python. Users can write Python code that gets translated to Lua scripts and executed atomically on Redis.

## Motivation

**Current Limitation:**
```python
# Requires fetching data to Python
items = await model_a.items[0:5]  # Fetch from Redis
model_b.results[10:15] = items     # Send back to Redis
```

**With Server-Side Operations:**
```python
# Executes entirely on Redis server
async with ServerOps() as ops:
    ops.assign(model_a.items[0:5], model_b.results[10:15])
# Single Lua script execution, no data transfer
```

## Architecture

### 1. Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    User Python Code                          │
│  async with ServerOps() as ops:                              │
│      ops.assign(model_a.items[0:5], model_b.results[10:])   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│               ServerOpContext (Context Manager)              │
│  - Collects operations during context                        │
│  - Validates operations                                      │
│  - Coordinates execution                                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  OperationRef System                         │
│  - ServerRef: References to model fields                     │
│  - SliceRef: References to slices (model.items[0:5])        │
│  - FieldRef: References to simple fields (model.counter)    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    Operation Classes                         │
│  - AssignOp: Copy from source to target                     │
│  - ConcatOp: Concatenate multiple sources                   │
│  - IncrByFieldOp: Increment by another field's value        │
│  - SwapOp: Atomic swap between two fields                   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   LuaScriptGenerator                         │
│  - Converts operations to Lua code                           │
│  - Optimizes multiple operations                             │
│  - Handles error cases                                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    Redis EVAL Command                        │
│  - Executes Lua script atomically                            │
│  - Returns results                                           │
└─────────────────────────────────────────────────────────────┘
```

### 2. Class Hierarchy

```python
# Base reference types
class ServerRef:
    """Base class for server-side references"""
    key: str           # Redis key (e.g., "ModelA:123")
    json_path: str     # JSON path (e.g., "$.items")
    model_class: Type  # Original model class

class FieldRef(ServerRef):
    """Reference to a simple field"""
    pass

class SliceRef(ServerRef):
    """Reference to a slice of a list/array"""
    start: Optional[int]
    stop: Optional[int]
    step: Optional[int] = 1

# Operation base
class ServerOp(ABC):
    """Base class for server-side operations"""

    @abstractmethod
    def to_lua(self) -> str:
        """Convert operation to Lua code"""
        pass

    @abstractmethod
    def get_keys(self) -> List[str]:
        """Get all Redis keys involved"""
        pass

# Concrete operations
class AssignOp(ServerOp):
    source: ServerRef
    target: ServerRef

class ConcatOp(ServerOp):
    sources: List[ServerRef]
    target: ServerRef
    separator: str = ""

class IncrByFieldOp(ServerOp):
    target: ServerRef
    increment_by: ServerRef

class SwapOp(ServerOp):
    ref_a: ServerRef
    ref_b: ServerRef
```

### 3. Reference Creation System

To make Python code translate to server references, we need to intercept operations on model fields:

```python
class ServerOpProxy:
    """Proxy object that creates ServerRef when accessed in ServerOps context"""

    def __init__(self, model: AtomicRedisModel):
        self._model = model

    def __getattribute__(self, name: str):
        # Check if we're in ServerOps context
        if _server_ops_context.get():
            # Create FieldRef
            return FieldRef(
                key=self._model.key,
                json_path=f"$.{name}",
                model_class=type(self._model)
            )
        # Normal attribute access
        return super().__getattribute__(name)

    def __getitem__(self, index):
        if _server_ops_context.get():
            if isinstance(index, slice):
                return SliceRef(
                    key=self._model.key,
                    json_path=f"$.{self._current_field}",
                    start=index.start,
                    stop=index.stop,
                    step=index.step
                )
        return super().__getitem__(index)
```

### 4. Context Manager

```python
class ServerOps:
    """Context manager for server-side operations"""

    def __init__(self, client: Optional[Redis] = None):
        self._client = client
        self._operations: List[ServerOp] = []
        self._token = None

    async def __aenter__(self):
        # Set context variable so ServerOpProxy knows we're active
        self._token = _server_ops_context.set(self)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        _server_ops_context.reset(self._token)

        if exc_type is None:
            # Generate and execute Lua script
            await self._execute()

    def assign(self, source: ServerRef, target: ServerRef):
        """Assign source to target on Redis server"""
        self._operations.append(AssignOp(source=source, target=target))

    def concat(self, *sources: ServerRef, target: ServerRef, separator: str = ""):
        """Concatenate multiple sources into target"""
        self._operations.append(ConcatOp(
            sources=list(sources),
            target=target,
            separator=separator
        ))

    def incr_by_field(self, target: ServerRef, increment_by: ServerRef):
        """Increment target by value of another field"""
        self._operations.append(IncrByFieldOp(
            target=target,
            increment_by=increment_by
        ))

    def swap(self, ref_a: ServerRef, ref_b: ServerRef):
        """Atomically swap two field values"""
        self._operations.append(SwapOp(ref_a=ref_a, ref_b=ref_b))

    async def _execute(self):
        """Generate Lua script and execute on Redis"""
        if not self._operations:
            return

        generator = LuaScriptGenerator(self._operations)
        script = generator.generate()
        keys = generator.get_all_keys()

        client = self._client or get_default_client()
        result = await client.eval(script, len(keys), *keys)

        return result
```

### 5. Lua Script Generation

```python
class LuaScriptGenerator:
    """Generates optimized Lua scripts from operations"""

    def __init__(self, operations: List[ServerOp]):
        self.operations = operations

    def generate(self) -> str:
        """Generate complete Lua script"""
        lines = [
            "-- Auto-generated server-side operations script",
            "",
        ]

        # Generate code for each operation
        for i, op in enumerate(self.operations):
            lines.append(f"-- Operation {i+1}: {op.__class__.__name__}")
            lines.append(op.to_lua())
            lines.append("")

        lines.append("return 'OK'")
        return "\n".join(lines)

    def get_all_keys(self) -> List[str]:
        """Get all unique Redis keys across all operations"""
        keys = set()
        for op in self.operations:
            keys.update(op.get_keys())
        return sorted(keys)  # Sorted for consistency
```

### 6. Operation Implementation Examples

#### AssignOp

```python
class AssignOp(ServerOp):
    source: ServerRef
    target: ServerRef

    def to_lua(self) -> str:
        # For simple field assignment
        if isinstance(self.source, FieldRef):
            return f"""
local value = redis.call('JSON.GET', '{self.source.key}', '{self.source.json_path}')
redis.call('JSON.SET', '{self.target.key}', '{self.target.json_path}', value)
"""

        # For slice assignment
        if isinstance(self.source, SliceRef):
            start = self.source.start or 0
            stop = self.source.stop or -1

            # Redis JSON slice syntax: [start:stop]
            slice_path = f"{self.source.json_path}[{start}:{stop}]"

            return f"""
local slice = redis.call('JSON.GET', '{self.source.key}', '{slice_path}')
local decoded = cjson.decode(slice)

-- For list slices, we need to replace the target range
local target_start = {self.target.start or 0}
redis.call('JSON.ARRINSERT', '{self.target.key}', '{self.target.json_path}', target_start, unpack(decoded))
"""

    def get_keys(self) -> List[str]:
        return [self.source.key, self.target.key]
```

#### ConcatOp

```python
class ConcatOp(ServerOp):
    sources: List[ServerRef]
    target: ServerRef
    separator: str = ""

    def to_lua(self) -> str:
        # Fetch all sources
        fetch_lines = []
        for i, source in enumerate(self.sources):
            fetch_lines.append(
                f"local src_{i} = redis.call('JSON.GET', '{source.key}', '{source.json_path}')"
            )

        # Concatenate
        source_vars = [f"src_{i}" for i in range(len(self.sources))]
        concat_expr = f" .. '{self.separator}' .. ".join(source_vars)

        return f"""
{chr(10).join(fetch_lines)}
local result = {concat_expr}
redis.call('JSON.SET', '{self.target.key}', '{self.target.json_path}', result)
"""

    def get_keys(self) -> List[str]:
        keys = [s.key for s in self.sources]
        keys.append(self.target.key)
        return keys
```

#### SwapOp

```python
class SwapOp(ServerOp):
    ref_a: ServerRef
    ref_b: ServerRef

    def to_lua(self) -> str:
        return f"""
-- Atomic swap
local val_a = redis.call('JSON.GET', '{self.ref_a.key}', '{self.ref_a.json_path}')
local val_b = redis.call('JSON.GET', '{self.ref_b.key}', '{self.ref_b.json_path}')
redis.call('JSON.SET', '{self.ref_a.key}', '{self.ref_a.json_path}', val_b)
redis.call('JSON.SET', '{self.ref_b.key}', '{self.ref_b.json_path}', val_a)
"""

    def get_keys(self) -> List[str]:
        return [self.ref_a.key, self.ref_b.key]
```

## Integration with Existing Infrastructure

### 1. Integration with Pipeline System

Server operations can work alongside regular pipelines:

```python
# Combine with pipeline operations
async with model_a.apipeline() as pipe_model:
    # Regular pipeline operations
    pipe_model.items.append("new_item")

    # Server-side operations
    async with ServerOps() as ops:
        ops.assign(model_b.counter, pipe_model.total)

# Both execute: pipeline commits, then server ops run
```

**Implementation approach:**
- ServerOps detects if a pipeline is active via `_context_var`
- If pipeline is active, ServerOps queues script execution to pipeline
- Otherwise, executes script directly

### 2. Model Integration

Add helper method to `AtomicRedisModel`:

```python
class AtomicRedisModel(BaseModel):
    # ... existing code ...

    def server_ref(self) -> ServerOpProxy:
        """Get a server-side reference to this model for server operations"""
        return ServerOpProxy(self)
```

**Usage:**
```python
model_a_ref = model_a.server_ref()
model_b_ref = model_b.server_ref()

async with ServerOps() as ops:
    ops.assign(model_a_ref.items[0:5], model_b_ref.results[10:15])
```

### 3. Type System Integration

Extend `RedisType` classes to support server references:

```python
class RedisList(list, GenericRedisType):
    # ... existing code ...

    def __getitem__(self, index):
        # Check if in ServerOps context
        if _server_ops_context.get():
            if isinstance(index, slice):
                return SliceRef(
                    key=self.key,
                    json_path=self.json_path,
                    start=index.start,
                    stop=index.stop
                )

        # Regular behavior
        return super().__getitem__(index)
```

## Usage Examples

### Example 1: List Slice Assignment

```python
from rapyer.server_ops import ServerOps

# Models
class TaskList(AtomicRedisModel):
    pending: RedisList[str]
    completed: RedisList[str]

# Create models
tasks_a = TaskList(pending=["task1", "task2", "task3"], completed=[])
tasks_b = TaskList(pending=[], completed=[])

await tasks_a.asave()
await tasks_b.asave()

# Move first 2 pending tasks from tasks_a to tasks_b
# Entirely on Redis server - no data transfer to Python
async with ServerOps() as ops:
    ops.assign(
        source=tasks_a.server_ref().pending[0:2],
        target=tasks_b.server_ref().pending[0:]
    )

# Verify
await tasks_a.aget(tasks_a.key)  # pending: ["task3"], completed: []
await tasks_b.aget(tasks_b.key)  # pending: ["task1", "task2"], completed: []
```

### Example 2: Counter Aggregation

```python
class Stats(AtomicRedisModel):
    views: RedisInt
    clicks: RedisInt
    total: RedisInt

stats1 = Stats(views=100, clicks=50, total=0)
stats2 = Stats(views=200, clicks=75, total=0)
summary = Stats(views=0, clicks=0, total=0)

await stats1.asave()
await stats2.asave()
await summary.asave()

# Calculate totals on server
async with ServerOps() as ops:
    # Sum views
    ops.incr_by_field(
        target=summary.server_ref().views,
        increment_by=stats1.server_ref().views
    )
    ops.incr_by_field(
        target=summary.server_ref().views,
        increment_by=stats2.server_ref().views
    )

    # Sum clicks
    ops.incr_by_field(
        target=summary.server_ref().clicks,
        increment_by=stats1.server_ref().clicks
    )
    ops.incr_by_field(
        target=summary.server_ref().clicks,
        increment_by=stats2.server_ref().clicks
    )
```

### Example 3: String Concatenation

```python
class Message(AtomicRedisModel):
    header: RedisStr
    body: RedisStr
    footer: RedisStr
    full_message: RedisStr

msg = Message(
    header="Hello",
    body="This is the content",
    footer="Goodbye",
    full_message=""
)
await msg.asave()

# Concatenate on server
async with ServerOps() as ops:
    ops.concat(
        msg.server_ref().header,
        msg.server_ref().body,
        msg.server_ref().footer,
        target=msg.server_ref().full_message,
        separator="\n\n"
    )
```

### Example 4: Atomic Swap

```python
class Account(AtomicRedisModel):
    balance: RedisFloat

account_a = Account(balance=100.0)
account_b = Account(balance=200.0)

await account_a.asave()
await account_b.asave()

# Swap balances atomically
async with ServerOps() as ops:
    ops.swap(
        account_a.server_ref().balance,
        account_b.server_ref().balance
    )

# Result: account_a.balance=200.0, account_b.balance=100.0
```

## Implementation Plan

### Phase 1: Core Infrastructure
1. Create `rapyer/server_ops/` package
2. Implement base classes:
   - `ServerRef`, `FieldRef`, `SliceRef`
   - `ServerOp` abstract base
   - Context variable `_server_ops_context`

### Phase 2: Operations
3. Implement concrete operations:
   - `AssignOp`
   - `ConcatOp`
   - `IncrByFieldOp`
   - `SwapOp`

### Phase 3: Lua Generation
4. Implement `LuaScriptGenerator`
5. Add Lua code generation for each operation
6. Add error handling and validation

### Phase 4: Context Manager
7. Implement `ServerOps` context manager
8. Add operation collection
9. Add script execution logic

### Phase 4: Integration
10. Add `server_ref()` method to `AtomicRedisModel`
11. Implement `ServerOpProxy`
12. Update `RedisType` classes to support server references
13. Integrate with pipeline system

### Phase 5: Testing & Documentation
14. Write comprehensive tests
15. Add usage examples
16. Update documentation

## File Structure

```
rapyer/
├── server_ops/
│   ├── __init__.py          # Public API exports
│   ├── context.py           # ServerOps context manager
│   ├── refs.py              # ServerRef, FieldRef, SliceRef
│   ├── operations.py        # ServerOp subclasses
│   ├── generator.py         # LuaScriptGenerator
│   └── proxy.py             # ServerOpProxy
├── base.py                  # Add server_ref() method
└── types/
    └── base.py              # Update RedisType for server refs

tests/
└── integration/
    └── server_ops/
        ├── test_assign.py
        ├── test_concat.py
        ├── test_incr_by_field.py
        ├── test_swap.py
        └── test_integration.py
```

## Benefits

1. **Performance**: No data transfer between Redis and Python
2. **Atomicity**: All operations in a single Lua script are atomic
3. **Pythonic API**: Users write normal Python code
4. **Type-Safe**: Leverages existing type system
5. **Composable**: Works with pipelines and other features
6. **Extensible**: Easy to add new operations

## Future Enhancements

1. **Conditional Operations**: `if` statements in server ops
2. **Loops**: `for` loops over Redis data structures
3. **Math Operations**: Complex calculations on server
4. **Custom Lua**: Allow users to inject custom Lua code
5. **Operation Optimization**: Detect and optimize common patterns
6. **Debugging**: Add logging and tracing for generated Lua scripts
