from qdrant_client.models import PointStruct


def load_and_index(client, collection_name, embed_fn, patterns):
    """
    Embed and upsert the scam patterns.

    Skips the work if the collection already holds them. Upserting is
    idempotent (fixed point IDs), so re-running was harmless but re-encoded
    every pattern on each startup -- the old Chroma indexer had this same
    guard and it was lost in the Qdrant migration.
    """
    try:
        existing = client.count(collection_name=collection_name).count
        if existing >= len(patterns):
            return
    except Exception:
        # A missing/unreadable collection just means we should index it.
        pass

    points = []

    texts = [
        p["text"] + " Example phrases: " + " | ".join(p["example_phrases"])
        for p in patterns
    ]

    embeddings = embed_fn.encode(texts)

    for i, pattern in enumerate(patterns):

        points.append(
            PointStruct(
                id=i + 1,
                vector=embeddings[i].tolist(),
                payload={
                    "pattern_id": pattern["id"],
                    "pattern_name": pattern["pattern_name"],
                    "category": pattern["category"],
                    "text": texts[i],
                },
            )
        )

    client.upsert(
        collection_name=collection_name,
        points=points,
    )