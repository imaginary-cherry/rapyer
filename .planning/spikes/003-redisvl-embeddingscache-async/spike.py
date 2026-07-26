"""Spike 003: redisvl EmbeddingsCache async round-trip (aset/aget/amget/ttl). Redis Stack :6370 only."""

import asyncio

from redisvl.extensions.cache.embeddings import EmbeddingsCache

URL = "redis://localhost:6370"
MODEL = "dummy-model"
VEC = [0.10, 0.20, 0.90, 0.10]


async def main():
    print("=== Spike 003: redisvl EmbeddingsCache (async) ===\n")
    import redisvl

    print(f"redisvl version: {redisvl.__version__}\n")

    cache = EmbeddingsCache(name="spike_embedcache", redis_url=URL)

    # single async round-trip
    key = await cache.aset(
        content="what is machine learning?",
        model_name=MODEL,
        embedding=VEC,
        metadata={"category": "ai"},
    )
    print(f"aset -> key={key}")
    got = await cache.aget(content="what is machine learning?", model_name=MODEL)
    round_trip_ok = (
        got is not None
        and got["content"] == "what is machine learning?"
        and list(got["embedding"]) == VEC
        and got["metadata"] == {"category": "ai"}
    )
    print(
        f"aget -> content={got and got['content']!r} embedding_len={got and len(got['embedding'])} metadata={got and got['metadata']}"
    )
    print(f"single round-trip ok: {round_trip_ok}\n")

    # batch async
    items = [
        {
            "content": "deep learning",
            "model_name": MODEL,
            "embedding": [0.1, 0.2, 0.3, 0.4],
        },
        {
            "content": "neural nets",
            "model_name": MODEL,
            "embedding": [0.4, 0.3, 0.2, 0.1],
        },
    ]
    keys = await cache.amset(items)
    mres = await cache.amget(["deep learning", "neural nets"], MODEL)
    batch_ok = len(keys) == 2 and all(r is not None for r in mres) and len(mres) == 2
    print(
        f"amset -> {len(keys)} keys; amget -> {sum(1 for r in mres if r)} hits; batch ok: {batch_ok}\n"
    )

    # exists + drop
    exists_before = await cache.aexists(content="deep learning", model_name=MODEL)
    await cache.adrop(content="deep learning", model_name=MODEL)
    exists_after = await cache.aexists(content="deep learning", model_name=MODEL)
    print(f"aexists before drop={exists_before}, after drop={exists_after}\n")

    # per-entry TTL
    ttl_cache = EmbeddingsCache(name="spike_embedcache_ttl", redis_url=URL, ttl=1)
    tkey = await ttl_cache.aset(content="ephemeral", model_name=MODEL, embedding=VEC)
    present = await ttl_cache.aexists_by_key(tkey)
    await asyncio.sleep(1.5)
    gone = not await ttl_cache.aexists_by_key(tkey)
    print(f"ttl: present immediately={present}, expired after 1.5s={gone}\n")

    await cache.aclear()
    await ttl_cache.aclear()

    all_ok = (
        round_trip_ok
        and batch_ok
        and (exists_before and not exists_after)
        and present
        and gone
    )
    print(f"=== ALL ASYNC OPS OK: {all_ok} ===")


if __name__ == "__main__":
    asyncio.run(main())
