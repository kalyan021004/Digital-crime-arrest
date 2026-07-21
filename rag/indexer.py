from qdrant_client.models import PointStruct


def load_and_index(client, collection_name, embed_fn, patterns):

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