import chromadb
from .config import COLLECTION_NAME


def create_client():
    return chromadb.PersistentClient(path="./chroma_db")


def create_collection(client, embed_fn):
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"}
    )