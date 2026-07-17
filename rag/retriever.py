def retrieve(collection, query, top_k=2):

    results = collection.query(
        query_texts=[query],
        n_results=top_k
    )

    matches = []

    ids = results["ids"][0]
    docs = results["documents"][0]
    metas = results["metadatas"][0]
    distances = results["distances"][0]

    for i in range(len(ids)):
        matches.append({
            "id": ids[i],
            "pattern_name": metas[i]["pattern_name"],
            "category": metas[i]["category"],
            "score": 1 - distances[i],   # cosine similarity
            "snippet": docs[i][:150]
        })

    return matches