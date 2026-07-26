---
spike: 002
name: hybrid-crosskey-prefilter
type: standard
validates: "Given vector in an SF key but filter fields in the parent JSON doc, when a hybrid KNN+boolean prefilter runs, then it completes as a single atomic server-side op (no two-step client round-trip)"
verdict: VALIDATED
related: [001]
tags: [vector, hybrid, atomicity, lua, redisearch]
---

# Spike 002: Atomic cross-key hybrid KNN + prefilter

## What This Validates

The vector lives in the SF key; the filterable fields are canonically in the parent
JSON doc. RediSearch KNN+prefilter operates within one index. Can we get hybrid
(KNN + boolean filter) as a **single atomic op**, honoring the "no multi-round-trip
per user action" requirement? Two candidate approaches compared.

## Research

RediSearch hybrid syntax: `(@tag:{v})=>[KNN k @vec $q AS dist]` — the prefilter
precedes the KNN clause and both evaluate in one `FT.SEARCH`. Open question was
whether `FT.SEARCH` is callable from inside a Lua `EVAL` (historically some module
commands were blocked in scripts). Validated empirically on :6370.

## How to Run

```
python spike.py
```

## What to Expect

Query vector is nearest to the `food` docs, but we filter `category=ai`. Both
approaches must return only `Article:1` / `Article:2`, KNN-ranked.

## Investigation Trail

- Built SF HASHes carrying vector + a **co-located** `category` TAG, and parent JSON
  docs holding `category` as the canonical copy.
- **Approach A:** single `FT.SEARCH (@category:{ai})=>[KNN 3 ...]`.
- **Approach B:** `EVAL` that runs `FT.SEARCH` KNN (overfetch), then for each
  candidate reads the parent JSON `$.category` and filters — all in one script.
- First B run returned empty. Probe (`scratchpad/probe_b.py`) showed `FT.SEARCH`
  **does** run inside Lua (count=4, real distances, `JSON.GET` returns `["ai"]`) — the
  bug was mine: with `SORTBY dist`, RediSearch returns `dist` first in the fields
  array, so a fixed-index parse read the wrong slot. Fixed by looking up fields by
  name. B then returned the correct filtered, ranked results.

## Results

**VALIDATED — both approaches are atomic and correct.**

| Approach | Mechanism | Atomic? | Correct? | Trade-off |
|----------|-----------|---------|----------|-----------|
| A: co-located TAG | single `FT.SEARCH (@tag)=>[KNN]` | ✅ one command | ✅ | Filterable fields must be **duplicated** into the SF HASH and kept in sync on parent update |
| B: FT.SEARCH in Lua | one `EVAL`: KNN → per-candidate parent `JSON.GET` + filter | ✅ one `EVALSHA` | ✅ | Filters on **parent-only** fields (no denormalization), but overfetch + N+1 `JSON.GET` inside the script; more complex |

### Key discovery

`FT.SEARCH` (including vector KNN) **is callable from inside a Lua script** on Redis
Stack 2.10 — this unlocks atomic "search-then-read/mutate" patterns generally, not
just this hybrid case.

### Signal for the build

- **Default to Approach A**: co-locate the fields a RedisText query needs to prefilter
  on into the SF HASH. Simplest, fastest, one native command. Requires the SF save to
  also write those filter fields (and re-sync when the parent changes them).
- **Approach B is the escape hatch** for filtering on arbitrary parent-only fields
  without denormalization — atomic via a Lua wrapper, at the cost of overfetch + N+1
  parent reads. Keep in the back pocket; don't build first.
- Either way the "single atomic op per user action" requirement is **satisfiable** for
  hybrid queries.
