from .loader import load_patterns
from .embeddings import SentenceTransformerEmbeddingFunction
from .vector_store import create_client, create_collection
from .indexer import load_and_index
from .retriever import retrieve
from .config import VECTOR_SIZE


class ScamPatternKB:

    def __init__(self):

        self.patterns = load_patterns()

        self.embed_fn = SentenceTransformerEmbeddingFunction()

        self.client = create_client()

        self.collection = create_collection(
            self.client,
            VECTOR_SIZE,
        )

        load_and_index(
            self.client,
            self.collection,
            self.embed_fn,
            self.patterns,
        )

    def retrieve(self, query, top_k=2):

        return retrieve(
            self.client,
            self.collection,
            self.embed_fn,
            query,
            top_k,
        )