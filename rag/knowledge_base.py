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


# ---------------------------------------------------------------------------
# Shared instance
# ---------------------------------------------------------------------------
# agents/nodes.py, server/api.py and mcp_server/server.py each used to do
# `_kb = ScamPatternKB()` at module scope. Importing the API pulls in
# agents.graph -> agents.nodes, so TWO knowledge bases were constructed in a
# single process. That:
#
#   1. crashed on startup in embedded Qdrant mode -- the second client hit the
#      exclusive lock on qdrant_data/ and raised
#      "Storage folder ... is already accessed by another instance";
#   2. loaded the sentence-transformer model twice, doubling both RAM and
#      startup time even when it did not crash (e.g. against a Qdrant server).
#
# get_kb() builds it once per process and hands the same object to every
# caller. Cheap to call repeatedly.

_kb_instance = None


def get_kb() -> "ScamPatternKB":
    """Return the process-wide ScamPatternKB, constructing it on first use."""
    global _kb_instance
    if _kb_instance is None:
        _kb_instance = ScamPatternKB()
    return _kb_instance