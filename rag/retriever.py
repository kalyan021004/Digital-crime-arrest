def retrieve(client, collection_name, embed_fn, query, top_k=2):

    query_vector = embed_fn.encode([query])[0]

    response = client.query_points(
        collection_name=collection_name,
        query=query_vector.tolist(),
        limit=top_k,
    )

    matches = []

    for point in response.points:

        payload = point.payload

        matches.append({
            "id": payload["pattern_id"],
            "pattern_name": payload["pattern_name"],
            "category": payload["category"],
            "score": point.score,
            "snippet": payload["text"][:150],
        })

    return matches