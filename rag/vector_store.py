from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from .config import (
    COLLECTION_NAME,
    VECTOR_SIZE,
    QDRANT_URL,
    QDRANT_API_KEY,
)


def create_client():
    return QdrantClient(
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY,
    )


def create_collection(client, vector_size):

    collections = [
        c.name
        for c in client.get_collections().collections
    ]

    if COLLECTION_NAME not in collections:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE,
            ),
        )

    return COLLECTION_NAME