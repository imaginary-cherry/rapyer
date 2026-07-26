"""Spike 002: atomic hybrid KNN+prefilter, vector-in-SF-key vs filter-in-parent. Redis Stack :6370 only."""

import asyncio
import json
import struct

import redis.asyncio as aredis

URL = "redis://localhost:6370"
DIM = 4

# rows: (parent, text, category, embedding); query nearest to ai docs 1/2
CORPUS = [
    ("Article:1", "machine learning basics", "ai", [0.10, 0.20, 0.90, 0.10]),
    ("Article:2", "deep neural networks", "ai", [0.15, 0.25, 0.85, 0.05]),
    ("Article:3", "italian pasta recipes", "food", [0.12, 0.22, 0.88, 0.09]),
    ("Article:4", "sourdough bread guide", "food", [0.11, 0.21, 0.87, 0.08]),
]
QUERY_VEC = [0.11, 0.21, 0.88, 0.09]
FILTER_CAT = "ai"


def f32(vec):
    return struct.pack(f"<{len(vec)}f", *vec)


def sf_key(parent):
    return f"__rapyer_special__:hyb:{parent}:body"


def _dec(x):
    return x.decode() if isinstance(x, (bytes, bytearray)) else x


async def cleanup(r):
    try:
        await r.execute_command("FT.DROPINDEX", "idx:hyb")
    except Exception:
        pass
    async for k in r.scan_iter(match="__rapyer_special__:hyb:*"):
        await r.delete(k)
    async for k in r.scan_iter(match="Article:*"):
        await r.delete(k)


async def setup(r):
    # SF HASH carries the vector + a CO-LOCATED category TAG (approach A needs this)
    await r.execute_command(
        "FT.CREATE",
        "idx:hyb",
        "ON",
        "HASH",
        "PREFIX",
        "1",
        "__rapyer_special__:hyb:",
        "SCHEMA",
        "parent",
        "TAG",
        "category",
        "TAG",
        "embedding",
        "VECTOR",
        "FLAT",
        "6",
        "TYPE",
        "FLOAT32",
        "DIM",
        str(DIM),
        "DISTANCE_METRIC",
        "COSINE",
    )
    for parent, text, cat, vec in CORPUS:
        # vector + co-located category in the SF key
        await r.hset(
            sf_key(parent),
            mapping={"parent": parent, "category": cat, "embedding": f32(vec)},
        )
        # the parent JSON doc ALSO holds category (the canonical copy)
        await r.execute_command(
            "JSON.SET",
            parent,
            "$",
            json.dumps({"title": text, "category": cat, "body_ref": sf_key(parent)}),
        )


def parse_search(res):
    out = []
    i = 1
    while i < len(res):
        fields = res[i + 1]
        d = {_dec(fields[j]): _dec(fields[j + 1]) for j in range(0, len(fields), 2)}
        out.append(d)
        i += 2
    return res[0], out


# --- approach A: single FT.SEARCH with co-located TAG prefilter (one atomic command) ---
async def hybrid_colocated(r, k=3):
    res = await r.execute_command(
        "FT.SEARCH",
        "idx:hyb",
        "(@category:{%s})=>[KNN %d @embedding $q AS dist]" % (FILTER_CAT, k),
        "PARAMS",
        "2",
        "q",
        f32(QUERY_VEC),
        "SORTBY",
        "dist",
        "RETURN",
        "2",
        "parent",
        "dist",
        "DIALECT",
        "2",
    )
    return parse_search(res)


# --- approach B: KNN inside Lua, then read+filter parent JSON in the same EVAL ---
LUA_KNN_THEN_PARENT_FILTER = (
    "local res = redis.call('FT.SEARCH', KEYS[1], ARGV[1], "
    "'PARAMS', 2, 'q', ARGV[2], 'SORTBY', 'dist', 'RETURN', 2, 'parent', 'dist', 'DIALECT', 2); "
    "local out = {}; local i = 2; "
    "while i <= #res do "
    "  local fields = res[i+1]; local parent, dist; "
    "  for j = 1, #fields, 2 do "
    "    if fields[j] == 'parent' then parent = fields[j+1] end; "
    "    if fields[j] == 'dist' then dist = fields[j+1] end; "
    "  end; "
    "  local cat = redis.call('JSON.GET', parent, '$.category'); "
    "  if cat and string.find(cat, ARGV[3], 1, true) then "
    "    table.insert(out, parent); table.insert(out, dist); "
    "  end; "
    "  i = i + 2; "
    "end; "
    "return out"
)


async def hybrid_lua(r, overfetch=4):
    knn_query = "*=>[KNN %d @embedding $q AS dist]" % overfetch
    return await r.eval(
        LUA_KNN_THEN_PARENT_FILTER,
        1,
        "idx:hyb",
        knn_query,
        f32(QUERY_VEC),
        FILTER_CAT,
    )


async def main():
    r = aredis.from_url(URL)
    await cleanup(r)
    await setup(r)
    print("=== Spike 002: atomic hybrid KNN + prefilter ===\n")
    print(f"query nearest to food docs (3/4) but we filter category={FILTER_CAT!r}\n")

    print("--- Approach A: co-located TAG, single FT.SEARCH (one command) ---")
    count, rows = await hybrid_colocated(r)
    print(f"  matched: {count}")
    for d in rows:
        print(f"    parent={d.get('parent')}  dist={d.get('dist')}")
    a_ok = (
        all(d.get("parent") in ("Article:1", "Article:2") for d in rows) and count >= 1
    )
    print(f"  only 'ai' docs returned, KNN-ranked: {a_ok}\n")

    print("--- Approach B: FT.SEARCH inside Lua + parent-JSON filter (one EVAL) ---")
    try:
        res = await hybrid_lua(r)
        pairs = [(_dec(res[i]), _dec(res[i + 1])) for i in range(0, len(res), 2)]
        print(f"  FT.SEARCH-in-Lua RAN. filtered results: {pairs}")
        b_ok = (
            all(p in ("Article:1", "Article:2") for p, _ in pairs) and len(pairs) >= 1
        )
        print(f"  cross-key parent filter correct: {b_ok}")
        b_feasible = True
    except Exception as e:
        print(f"  FT.SEARCH-in-Lua FAILED: {type(e).__name__}: {e}")
        b_feasible = False

    print(f"\n  approach B (FT.SEARCH callable from Lua) feasible: {b_feasible}")

    await cleanup(r)
    await r.aclose()
    print("\n=== done ===")


if __name__ == "__main__":
    asyncio.run(main())
