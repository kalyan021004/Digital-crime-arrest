import os

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from .config import (
    COLLECTION_NAME,
    VECTOR_SIZE,
    QDRANT_URL,
    QDRANT_API_KEY,
    QDRANT_LOCAL_PATH,
)


def create_client():
    """
    Return a Qdrant client, preferring a configured server and falling back to
    an embedded file-backed store.

    Why the fallback: QDRANT_URL has no default, so on a fresh clone with no
    .env the client was constructed against a null URL and the RAG layer died
    at import -- taking main.py, the API and the MCP server down with it,
    because ScamPatternKB() is instantiated at module scope in all three.
    A missing vector store should not be an unrecoverable startup crash any
    more than a missing MongoDB is (see db/mongo.py).

    qdrant-client supports an embedded mode that needs no server at all, so
    `git clone && pip install -r requirements.txt && python main.py` now works
    on a laptop with no Docker and no network. Set QDRANT_URL when you want
    the real thing (shared state across processes, the dashboard, deployment).

    NOTE: embedded mode holds an exclusive lock on its data directory, so only
    one process can use it at a time. Running main.py and uvicorn together
    requires a real Qdrant server -- start one with:
        docker run -p 6333:6333 qdrant/qdrant
    """
    if QDRANT_URL:
        try:
            client = QdrantClient(
                # Passing api_key="" upsets some client versions; send None.
                url=QDRANT_URL,
                api_key=QDRANT_API_KEY or None,
                timeout=5,
            )
            # Force an actual round trip. Constructing the client does NOT
            # connect, so without this the failure surfaces later as an opaque
            # ResponseHandlingException from deep inside create_collection().
            client.get_collections()
            print(f"[rag] Connected to Qdrant at {QDRANT_URL}")
            return client
        except Exception as exc:
            print(f"[rag] WARNING: Qdrant at {QDRANT_URL} is unreachable.")
            print(f"[rag] Reason: {type(exc).__name__}: {exc}")
            print("[rag] Falling back to embedded Qdrant. Data will NOT be")
            print("[rag] shared with other processes. Start a server with:")
            print("[rag]     docker run -p 6333:6333 qdrant/qdrant")

    return _embedded_client()


def _embedded_client():
    """File-backed Qdrant that needs no server."""
    os.makedirs(QDRANT_LOCAL_PATH, exist_ok=True)
    print(
        "[rag] Using embedded Qdrant at "
        f"{os.path.abspath(QDRANT_LOCAL_PATH)}"
    )
    return QdrantClient(path=QDRANT_LOCAL_PATH)


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