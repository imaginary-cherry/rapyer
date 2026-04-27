# ActionGroup API Reference

`ActionGroup` is a `Flag` enum used to control which categories of operations refresh a model's TTL. Pass it to `refresh_ttl` on `RedisConfig` (`Meta`) to get finer-grained control than the plain `True` / `False` toggle.

```python
from rapyer.actions import ActionGroup

class Session(AtomicRedisModel):
    user_id: str

Session.Meta.ttl = 1800
Session.Meta.refresh_ttl = ActionGroup.UPDATE | ActionGroup.APPEND
```

## Members

#### `READ`

Reading a value from Redis — full-model loads, field-level reads, lookups, contains-checks.

| Source | Methods |
|---|---|
| `AtomicRedisModel` | `aget`, `aload`, `afind`, `afind_one`, `afind_keys`, `aexists` |
| Module-level | `rapyer.aget`, `rapyer.afind`, `rapyer.afind_one`, `rapyer.aexists` |
| `BaseRedisType` | `aload` |
| `RedisDict` | `apop`, `apopitem` |
| `RedisList` | `apop` |
| `RedisPriorityQueue` | `apop`, `apeek`, `asize`, `aitems` |

#### `FETCH`

Loading a full model from Redis (a strict subset of `READ`).

| Source | Methods |
|---|---|
| `AtomicRedisModel` | `aget`, `afind`, `afind_one` |
| Module-level | `rapyer.aget`, `rapyer.afind`, `rapyer.afind_one` |

#### `CREATE`

Creating a model. The initial TTL is always set when a model is first created, even if `refresh_ttl=False`.

| Source | Methods |
|---|---|
| `AtomicRedisModel` | `asave`, `ainsert`, `aduplicate`, `aduplicate_many` |
| Module-level | `rapyer.ainsert` |

#### `UPDATE`

Modifying existing data. Triggered by virtually every mutating method, since updating data is the common denominator of all writes.

| Source | Methods |
|---|---|
| `AtomicRedisModel` | `asave`, `aupdate`, `aset_ttl` |
| `BaseRedisType` | `asave` |
| `RedisDict` | `update`, `clear`, `__setitem__`, `aset_item`, `adel_item`, `aupdate`, `apop`, `apopitem`, `aclear` |
| `RedisList` | `__setitem__`, `__iadd__`, `append`, `extend`, `insert`, `clear`, `remove_range`, `aappend`, `aextend`, `apop`, `ainsert`, `aclear` |
| `RedisStr` | `__iadd__`, `__imul__` |
| `RedisBytes` | `__iadd__` |
| `RedisInt` | `aincrease`, `__iadd__`, `__isub__`, `__imul__`, `__ifloordiv__`, `__imod__`, `__ipow__` |
| `RedisFloat` | `aincrease`, `__iadd__`, `__isub__`, `__imul__`, `__itruediv__`, `__ifloordiv__`, `__imod__`, `__ipow__` |
| `RedisDatetime` | `__iadd__`, `__isub__` |
| `RedisPriorityQueue` | `apush`, `apush_many`, `apop`, `aclear`, `aremove` |

#### `APPEND`

Adding new items to a collection.

| Source | Methods |
|---|---|
| `RedisList` | `__iadd__`, `append`, `extend`, `insert`, `aappend`, `aextend`, `ainsert` |
| `RedisStr` | `__iadd__` |
| `RedisBytes` | `__iadd__` |
| `RedisPriorityQueue` | `apush`, `apush_many` |

#### `ERASE`

Removing item(s) from a collection while keeping the model itself.

| Source | Methods |
|---|---|
| `RedisDict` | `clear`, `adel_item`, `apop`, `apopitem`, `aclear` |
| `RedisList` | `clear`, `remove_range`, `apop`, `aclear` |
| `RedisPriorityQueue` | `apop`, `aclear`, `aremove` |

#### `ARITHMETIC`

In-place numeric operations.

| Source | Methods |
|---|---|
| `RedisInt` | `aincrease`, `__iadd__`, `__isub__`, `__imul__`, `__ifloordiv__`, `__imod__`, `__ipow__` |
| `RedisFloat` | `aincrease`, `__iadd__`, `__isub__`, `__imul__`, `__itruediv__`, `__ifloordiv__`, `__imod__`, `__ipow__` |
| `RedisDatetime` | `__iadd__`, `__isub__` |

#### `DELETE`

Removing the entire model/key from Redis.

| Source | Methods |
|---|---|
| `AtomicRedisModel` | `adelete`, `adelete_by_key`, `adelete_many` |
| Module-level | `rapyer.adelete_many` |

> **Cannot be used with `refresh_ttl`.** The key is removed on delete, so refreshing its TTL is meaningless. Passing `ActionGroup.DELETE` to `refresh_ttl` raises `InvalidRefreshTtlError`.

## `ActionGroup.all(*, for_ttl=False)`

Returns the combined flag set of every member.

**Parameters:**
- `for_ttl` (bool): If `True`, excludes `DELETE` so the result is safe to assign to `refresh_ttl`. Defaults to `False`.

**Example:**

```python
from rapyer.actions import ActionGroup

# Equivalent to refresh_ttl=True
Session.Meta.refresh_ttl = ActionGroup.all(for_ttl=True)
```

## Combining Flags

`ActionGroup` is a `Flag` enum, so members combine with `|` and check with `&`:

```python
strategy = ActionGroup.READ | ActionGroup.FETCH
bool(strategy & ActionGroup.READ)   # True
bool(strategy & ActionGroup.UPDATE)  # False
```
