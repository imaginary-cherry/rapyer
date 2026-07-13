# TTL Cascade

TTL cascade lets a [reference](foreign-keys.md) graph share expiration behavior: setting
or refreshing a cascade-enabled parent's TTL atomically, server-side, re-arms every
reached child to **its own** `Meta.ttl`. This is a **per-child cascading refresh**, not
propagation of the parent's TTL value onto its children — a child with a shorter
`Meta.ttl` than its parent still expires on its own schedule.

## Enabling Cascade

Cascade is opt-in and disabled by default. There are two ways to enable it:

**Per-field**, by annotating a `Reference` field with `CascadeTTL`:

```python
from typing import Annotated, ClassVar

from rapyer import AtomicRedisModel
from rapyer.cascade import CascadeTTL
from rapyer.config import RedisConfig
from rapyer.types import Reference


class Author(AtomicRedisModel):
    name: str = "anon"

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=3600)


class Book(AtomicRedisModel):
    title: str = "untitled"
    author: Annotated[Reference[Author], CascadeTTL()]

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=3600)
```

**Globally**, via a default passed to `init_rapyer`:

```python
await init_rapyer(redis, cascade_ttl=CascadeTTL())
```

A global default applies to every `Reference` field that has no explicit per-field
`CascadeTTL` marker.

`CascadeTTL` carries three fields:

| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `enabled` | `bool` | `True` | Whether this edge participates in cascade. |
| `depth` | `int \| None` | `None` | How many hops the cascade continues past this edge. `None` means unbounded traversal. |
| `mode` | `TTLCascadeMode` | `TTLCascadeMode.EXTEND` | How the cascaded refresh interacts with a child's TTL. `EXTEND` is currently the only implemented mode — it exists as the seam for future modes (e.g. `OVERWRITE`/`IF_UNSET`), which are not implemented. |

Passing `CascadeTTL(enabled=False)` on a field explicitly disables cascade for that edge
even when a global default is set.

## Precedence

Cascade eligibility for a given `Reference` field is resolved in this order:

1. An explicit per-field `CascadeTTL` marker (`Annotated[Reference[T], CascadeTTL(...)]`)
   always wins.
2. Absent that, the global default set via `init_rapyer(cascade_ttl=...)` applies.
3. Absent both, the edge is not cascade-enabled at all.

This is the **field > global > off** precedence rule. Crucially, when no cascade marker
applies at all, plain `Meta.ttl` / `refresh_ttl` behavior on that model is completely
unaffected — cascade is additive and never changes non-cascade TTL semantics.

## Per-Child Cascading Refresh

Two independent surfaces trigger a cascade — an opt-in explicit call and an automatic
path:

```python
# Opt-in: pass cascade=True and a caller-supplied ttl for the root.
result = await book.aset_ttl(3600, cascade=True)

# Automatic: fires whenever the model has outgoing cascade-enabled edges,
# on every asave() / refresh_ttl() call — no extra argument needed.
await book.asave()
```

In both cases:

- The **root's own keys** (its main document key, plus any of its own special-field
  keys) are refreshed to the caller-supplied `ttl` (`aset_ttl(ttl, cascade=True)`) or to
  the root's own `Meta.ttl` (the automatic `refresh_ttl` path).
- **Every cascade-reached child** — and any of its own special-field keys — refreshes to
  **its own** configured `Meta.ttl`, taken from the plan baked at `init_rapyer()` time.
  The child's TTL is never overwritten with the root's TTL.

The whole operation — traversal and every `EXPIRE` — runs as a single atomic,
server-side Lua script. There is no read-then-branch gap between discovering the graph
and applying the refresh.

`aset_ttl(ttl, cascade=True)` returns a `CascadeResult(dangling_children, dangling_special)`
describing how many reached keys no longer exist (a dangling reference whose target was
deleted). The automatic `refresh_ttl`/`asave()` path discards this result — it still runs
the same atomic script, but the dangling counts aren't surfaced to the caller.

!!! note "Cascade-reachable targets must declare `Meta.ttl`"
    `init_rapyer()` validates the whole cascade graph up front and raises if any
    cascade-reachable class — or any class with outgoing cascade-enabled edges — has no
    `Meta.ttl`. A `None` TTL would otherwise become a nil-argument Lua runtime error at
    write time; failing fast at startup catches this instead.

## Cluster Boundary

!!! warning "Standalone Redis only"
    Rapyer keys carry no Redis Cluster hash tags. A cascade spanning a parent plus any
    number of children touches keys that Cluster has no guarantee of co-locating on the
    same shard, so a multi-key cascade script will hit `CROSSSLOT` on a clustered
    deployment. This is a hard, by-construction limitation of the current
    standalone-Redis-only design — not a "not yet implemented" gap that a future release
    closes.

## Extension Points (Not Yet Implemented)

TTL cascade is the first of a planned family of cascade strategies. The backbone —
`CascadeSpec`, the shared `enabled`/`depth` surface, and the traversal-shared /
apply-swapped shape — is deliberately built so that future `CascadeDelete` and
`CascadeSave` strategies can reuse the same graph-walk without redesigning it: only the
*apply* step (what happens to a reached key) would differ per strategy.

**No `CascadeDelete` or `CascadeSave` class exists in the current release.** The sketch
below illustrates the shape such a strategy would take — it is not shipped, not
importable, and shown purely to demonstrate the seam:

```python
# Illustrative only — CascadeDelete does not exist in this release.
@dataclasses.dataclass(frozen=True)
class CascadeDelete(CascadeSpec):
    """Would reuse `enabled`/`depth` from CascadeSpec; the apply step would
    delete each reached key instead of refreshing its TTL."""
```

Reaching for cascade delete or cascade save today means implementing that behavior at
the application layer — the framework only ships the TTL strategy this milestone.
