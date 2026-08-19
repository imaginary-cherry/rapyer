# TTL Cascade

TTL cascade lets a [reference](foreign-keys.md) graph share expiration behavior: setting
or refreshing a cascade-enabled parent's TTL atomically, server-side, re-arms every
reached child to **its own** `Meta.ttl`. This is a **per-child cascading refresh**, not
propagation of the parent's TTL value onto its children — a child with a shorter
`Meta.ttl` than its parent still expires on its own schedule.

!!! warning "Requires real Redis 7+ (Redis Functions)"
    TTL cascade **traversal** is implemented as a Redis Functions library
    (`FUNCTION LOAD` + `FCALL`) and requires a real Redis 7 or newer. It is **not**
    supported under `fakeredis`, which has no Redis Functions.

    On `fakeredis`, a cascade-enabled model still refreshes its **own** main +
    special-field keys per `Meta.ttl` / `refresh_ttl`, but **edges are not
    followed** (no traversal). In particular, `aset_ttl(cascade=True)` on
    `fakeredis` refreshes only the root's own keys and reports zero danglings
    (`CascadeResult(0, 0)`). Non-cascade `Meta.ttl` / `refresh_ttl` behavior is
    unchanged on both backends.

    This identical divergence applies to SF-held-ref cascade (`RedisSet`/
    `RedisPriorityQueue` members): on fakeredis the container's own key still
    refreshes via a plain `EXPIRE`, but its members are never followed — no
    traversal, same as inline cascade.

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

## Cascade-Eligible Shapes

Cascade traversal follows every shape a `ForeignKey` (`Reference`) can take — whether the
reference lives inline in the parent's JSON document or inside a special-field container
with its own Redis key:

| Shape | Example | Cascade-eligible |
|-------|---------|-------------------|
| Direct FK field | `Reference[Author]` | Yes |
| Collection-of-FK | `list[Reference[Author]]` / `dict[K, Reference[Author]]` | Yes |
| Nested-submodel FK | An inline sub-model whose own field is `Reference`-annotated | Yes |
| `RedisSet[Reference[Author]]` | FK references held as members of a Redis SET | Yes |
| `RedisPriorityQueue[Reference[Author]]` | FK references held as members of a Redis sorted set | Yes |

All five shapes resolve cascade eligibility through the same **field > global > off**
precedence rule described above — a `RedisSet`/`RedisPriorityQueue` field is annotated
with `CascadeTTL` exactly like an inline `Reference` field.

### Worked Example: Cascading Through a `RedisSet`

```python
from typing import Annotated, ClassVar

from pydantic import Field
from rapyer import AtomicRedisModel
from rapyer.cascade import CascadeTTL
from rapyer.config import RedisConfig
from rapyer.types import Reference, RedisSet


class Author(AtomicRedisModel):
    name: str = "anon"

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=3600)


class Library(AtomicRedisModel):
    name: str = "main"
    authors: Annotated[RedisSet[Reference[Author]], CascadeTTL()] = Field(
        default_factory=RedisSet
    )

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=3600)


library = await Library(name="main").asave()
author = await Author(name="Jane").asave()
await library.authors.aadd(author.key)

# Every member of the set is re-armed to its own Meta.ttl, exactly like an
# inline collection-of-FK field, whenever the parent's TTL is (re)set:
await library.asave()
# ...or explicitly:
await library.aset_ttl(3600, cascade=True)
```

The same applies to a `RedisPriorityQueue[Reference[Author]]` field: members added via
`apush` are reached the same way and re-armed to their own `Meta.ttl`.

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
server-side Redis Function (`FCALL`), with the cascade plan baked into the loaded
library and decoded once. There is no read-then-branch gap between discovering the
graph and applying the refresh.

`aset_ttl(ttl, cascade=True)` returns a `CascadeResult(dangling_children, dangling_special)`
describing how many reached keys no longer exist (a dangling reference whose target was
deleted). The automatic `refresh_ttl`/`asave()` path discards this result — it still runs
the same atomic script, but the dangling counts aren't surfaced to the caller.

!!! note "Cascade-reachable targets must declare `Meta.ttl`"
    `init_rapyer()` validates the whole cascade graph up front and raises if any
    cascade-reachable class — or any class with outgoing cascade-enabled edges — has no
    `Meta.ttl`. A `None` TTL would otherwise become a nil-argument Lua runtime error at
    write time; failing fast at startup catches this instead.

## Cost and Scaling

A cascade is **linear in the number of keys it reaches**. For every reached node the
server-side function issues one `EXPIRE`, plus one `JSON.GET` for each node that has
outgoing reference paths to read. There is no per-node round trip — the whole walk
happens inside a single `FCALL` — but there is also no batching: a graph twice as large
costs roughly twice as much.

The chart plots measured wall time against the number of reached keys, both axes
logarithmic. A straight line means cost rises in direct proportion to graph size; the
measured slope is 1.03, so ten times the links costs very close to ten times the time.

<svg viewBox="0 0 700 280" role="img" aria-label="Cascade wall time against number of reached keys, log-log. Time rises in direct proportion to graph size: 1000 keys take 6 milliseconds, 500000 keys take 3.6 seconds, and one million keys is projected at about 7 seconds, above the 5 second mark where Redis begins replying BUSY.">
<g stroke="currentColor" stroke-opacity="0.18" stroke-width="1">
<line x1="90" y1="190" x2="660" y2="190"/>
<line x1="90" y1="140" x2="660" y2="140"/>
<line x1="90" y1="90" x2="660" y2="90"/>
<line x1="90" y1="40" x2="660" y2="40"/>
</g>
<g stroke="currentColor" stroke-width="1.2">
<line x1="90" y1="240" x2="660" y2="240"/>
<line x1="90" y1="240" x2="90" y2="36"/>
</g>
<g font-family="ui-monospace,SFMono-Regular,Menlo,monospace" font-size="10" fill="currentColor" fill-opacity="0.75" text-anchor="end">
<text x="84" y="193">10ms</text>
<text x="84" y="143">100ms</text>
<text x="84" y="93">1s</text>
<text x="84" y="43">10s</text>
</g>
<g font-family="ui-monospace,SFMono-Regular,Menlo,monospace" font-size="10" fill="currentColor" fill-opacity="0.75" text-anchor="middle">
<text x="90" y="256">1k</text>
<text x="220" y="256">5k</text>
<text x="333" y="256">20k</text>
<text x="407" y="256">50k</text>
<text x="520" y="256">200k</text>
<text x="594" y="256">500k</text>
<text x="650" y="256">1M</text>
<text x="375" y="272" fill-opacity="0.6">keys reached by the cascade</text>
</g>
<line x1="90" y1="55" x2="660" y2="55" stroke="#c0562a" stroke-width="1.4" stroke-dasharray="5 4"/>
<text x="656" y="50" font-family="ui-monospace,SFMono-Regular,Menlo,monospace" font-size="10" fill="#c0562a" text-anchor="end">5s — Redis starts replying BUSY to other clients</text>
<polyline points="90,201 220,170 333,143 407,121 520,85 594,62" fill="none" stroke="#4a7fb5" stroke-width="2.2"/>
<line x1="594" y1="62" x2="650" y2="48" stroke="#4a7fb5" stroke-width="1.6" stroke-dasharray="4 3"/>
<g fill="#4a7fb5">
<circle cx="90" cy="201" r="3.5"/>
<circle cx="220" cy="170" r="3.5"/>
<circle cx="333" cy="143" r="3.5"/>
<circle cx="407" cy="121" r="3.5"/>
<circle cx="520" cy="85" r="3.5"/>
<circle cx="594" cy="62" r="3.5"/>
</g>
<circle cx="650" cy="48" r="3.5" fill="none" stroke="#4a7fb5" stroke-width="1.8"/>
<g font-family="ui-monospace,SFMono-Regular,Menlo,monospace" font-size="9.5" fill="currentColor" fill-opacity="0.8">
<text x="98" y="197">6ms</text>
<text x="520" y="78">1.3s</text>
<text x="560" y="57">3.6s</text>
<text x="628" y="38">~7s</text>
</g>
</svg>

Measured on Redis Stack 7.2 in Docker on a laptop, one root over edge-free children.
Treat the slope as the takeaway and the absolute numbers as indicative — they move with
hardware. The hollow point at 1M is projected from the slope, not measured on this shape.

Graph *shape* changes the constant, not the growth rate, because interior nodes each pay
a `JSON.GET` that leaves do not:

| shape at ~1M nodes | wall time |
| --- | --- |
| One root over 1,000,000 edge-free children | 3.2s |
| A 1,000,000-node chain, one reference per node | 7.9s |
| A branching tree, 1,111,111 nodes | 10.3s |

These three shapes are covered by `benchmarks/test_cascade_ttl_large.py`; set
`BENCHMARK_CASCADE_LARGE_SIZE` to run them at a different size.

!!! warning "A cascade over a very large graph blocks the whole server"
    Redis executes the function on its single command thread, so nothing else is served
    until the walk finishes. Below `busy-reply-threshold` (5 seconds by default) every
    client simply blocks, including one trying to intervene. Past it, clients receive
    `BUSY`. `FUNCTION KILL` then works only while the function is still reading — the
    walk collects every key before writing any — but once it starts issuing `EXPIRE`s a
    kill is refused, leaving `SHUTDOWN NOSAVE` as the only escape. Keep cascade-reachable
    graphs well under that bound, or raise the threshold deliberately.

!!! danger "Every write re-walks the whole subtree"
    The automatic path fires on *each* `asave()` / `refresh_ttl()` of a model that has
    cascade-enabled edges, and each firing walks everything currently reachable. Building
    a connected graph one node at a time is therefore quadratic: inserting a 1,000-node
    chain node by node issues 500,500 `EXPIRE` calls (1 + 2 + … + 1000), not 1,000. At a
    million nodes that is ~5×10¹¹ expiries — effectively unbounded.

    When bulk-loading, keep the cascade off the per-node path: set `Meta.refresh_ttl` to
    an `ActionGroup` that excludes creates (for example `ActionGroup.UPDATE`), or write
    the nodes unlinked and attach the references last. Either way the cascade runs once
    over the finished graph instead of once per node.

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
