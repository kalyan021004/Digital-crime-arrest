def load_and_index(collection, patterns):

    if collection.count() >= len(patterns):
        return

    ids = []
    docs = []
    metadata = []

    for p in patterns:

        ids.append(p["id"])

        docs.append(
            p["text"] +
            " Example phrases: " +
            " | ".join(p["example_phrases"])
        )

        metadata.append({
            "pattern_name": p["pattern_name"],
            "category": p["category"]
        })

    collection.add(
        ids=ids,
        documents=docs,
        metadatas=metadata
    )