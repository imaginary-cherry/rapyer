"""Spike 001: KNN over separate SF keys (HASH vs JSON) + atomic combined save. Redis Stack :6370 only."""

import asyncio
import struct

import redis.asyncio as aredis

URL = "redis://localhost:6370"
DIM = 4

# corpus rows: (parent model key, text, category, embedding dim=4); query is nearest to doc 0/1
CORPUS = [
    ("Article:1", "machine learning basics", "ai", [0.10, 0.20, 0.90, 0.10]),
    ("Article:2", "deep neural networks", "ai", [0.15, 0.25, 0.85, 0.05]),
    ("Article:3", "italian pasta recipes", "food", [0.90, 0.10, 0.05, 0.05]),
    ("Article:4", "sourdough bread guide", "food", [0.85, 0.15, 0.10, 0.05]),
]
QUERY_TEXT = "intro to machine learning"
QUERY_VEC = [0.11, 0.21, 0.88, 0.09]  # deliberately near doc 0/1


def f32(vec):
    """Pack a float list into a little-endian FLOAT32 blob (RediSearch format)."""
    return struct.pack(f"<{len(vec)}f", *vec)


def sf_key(space, parent):
    # mimic SpecialFieldType.special_field_key: __rapyer_special__:{model_key}:{field}
    return f"__rapyer_special__:{space}:{parent}:body"


async def drop_index(r, name):
    try:
        await r.execute_command("FT.DROPINDEX", name)
    except Exception:
        pass


async def cleanup(r):
    await drop_index(r, "idx:sf_hash")
    await drop_index(r, "idx:sf_json")
    async for k in r.scan_iter(match="__rapyer_special__:*"):
        await r.delete(k)
    async for k in r.scan_iter(match="Article:*"):
        await r.delete(k)


# --- HASH variant ---
async def setup_hash(r):
    await r.execute_command(
        "FT.CREATE",
        "idx:sf_hash",
        "ON",
        "HASH",
        "PREFIX",
        "1",
        "__rapyer_special__:hash:",
        "SCHEMA",
        "parent",
        "TAG",
        "category",
        "TAG",
        "text",
        "TEXT",
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
        await r.hset(
            sf_key("hash", parent),
            mapping={
                "parent": parent,
                "category": cat,
                "text": text,
                "embedding": f32(vec),
            },
        )


async def knn_hash(r, k=3):
    res = await r.execute_command(
        "FT.SEARCH",
        "idx:sf_hash",
        "*=>[KNN {} @embedding $q AS dist]".format(k),
        "PARAMS",
        "2",
        "q",
        f32(QUERY_VEC),
        "SORTBY",
        "dist",
        "RETURN",
        "3",
        "parent",
        "text",
        "dist",
        "DIALECT",
        "2",
    )
    return parse_search(res)


# --- JSON variant ---
async def setup_json(r):
    await r.execute_command(
        "FT.CREATE",
        "idx:sf_json",
        "ON",
        "JSON",
        "PREFIX",
        "1",
        "__rapyer_special__:json:",
        "SCHEMA",
        "$.parent",
        "AS",
        "parent",
        "TAG",
        "$.category",
        "AS",
        "category",
        "TAG",
        "$.text",
        "AS",
        "text",
        "TEXT",
        "$.embedding",
        "AS",
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
        await r.execute_command(
            "JSON.SET",
            sf_key("json", parent),
            "$",
            _json({"parent": parent, "category": cat, "text": text, "embedding": vec}),
        )


async def knn_json(r, k=3):
    res = await r.execute_command(
        "FT.SEARCH",
        "idx:sf_json",
        "*=>[KNN {} @embedding $q AS dist]".format(k),
        "PARAMS",
        "2",
        "q",
        f32(QUERY_VEC),
        "SORTBY",
        "dist",
        "RETURN",
        "3",
        "parent",
        "text",
        "dist",
        "DIALECT",
        "2",
    )
    return parse_search(res)


# --- atomic combined save: SF vector + parent ref in ONE EVAL (single server op) ---
ATOMIC_SAVE = (
    "redis.call('HSET', KEYS[1], 'parent', ARGV[1], 'category', ARGV[2], 'text', ARGV[3], 'embedding', ARGV[4]); "
    "redis.call('JSON.SET', KEYS[2], '$', ARGV[5]); "
    "return 1"
)


async def atomic_save_demo(r):
    parent = "Article:99"
    sfk = sf_key("hash", parent)
    parent_doc = _json({"title": "atomic doc", "body_ref": sfk})
    await r.eval(
        ATOMIC_SAVE,
        2,
        sfk,
        parent,
        parent,
        "ai",
        "atomic write",
        f32([0.12, 0.22, 0.87, 0.08]),
        parent_doc,
    )
    # verify both landed
    stored_ref = await r.execute_command("JSON.GET", parent, "$.body_ref")
    has_vec = await r.hexists(sfk, "embedding")
    return stored_ref, has_vec


def parse_search(res):
    """FT.SEARCH RESP2: [count, key1, [f,v,...], key2, [...], ...]."""
    out = []
    count = res[0]
    i = 1
    while i < len(res):
        key = _dec(res[i])
        fields = res[i + 1]
        d = {}
        for j in range(0, len(fields), 2):
            d[_dec(fields[j])] = _dec(fields[j + 1])
        out.append((key, d))
        i += 2
    return count, out


def _dec(x):
    return x.decode() if isinstance(x, (bytes, bytearray)) else x


def _json(obj):
    import json

    return json.dumps(obj)


async def main():
    r = aredis.from_url(URL)
    await cleanup(r)
    print("=== Spike 001: KNN over separate SF keys ===\n")

    for label, setup, knn in [
        ("HASH", setup_hash, knn_hash),
        ("JSON", setup_json, knn_json),
    ]:
        await setup(r)
        count, results = await knn(r)
        print(f"--- {label} index --- (total matched: {count})")
        for key, d in results:
            print(f"  sf_key={key}")
            print(
                f"     -> parent={d.get('parent')}  dist={d.get('dist')}  text={d.get('text')!r}"
            )
        top_parent = results[0][1].get("parent")
        top_ok = top_parent in ("Article:1", "Article:2")
        print(f"  nearest parent resolves correctly: {top_ok} (got {top_parent})\n")

    print("--- Atomic combined save (SF vector + parent ref in one EVAL) ---")
    ref, has_vec = await atomic_save_demo(r)
    print(f"  parent JSON body_ref: {_dec(ref)}")
    print(f"  SF key has embedding: {has_vec}")
    print(f"  atomic save both-keys-present: {bool(ref) and has_vec}\n")

    await cleanup(r)
    await r.aclose()
    print("=== done ===")


if __name__ == "__main__":
    asyncio.run(main())
