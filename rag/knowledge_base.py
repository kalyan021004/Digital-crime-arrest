from .loader import load_patterns
from .embeddings import SentenceTransformerEmbeddingFunction
from .vector_store import create_client, create_collection
from .indexer import load_and_index
from .retriever import retrieve


class ScamPatternKB:

    def __init__(self):

        self.patterns = load_patterns()

        corpus = [
            p["text"] + " Example phrases: " +
            " | ".join(p["example_phrases"])
            for p in self.patterns
        ]

        self.embed_fn = SentenceTransformerEmbeddingFunction("BAAI/bge-small-en-v1.5")

        self.client = create_client()


        self.collection = create_collection(
            self.client,
            self.embed_fn
        )

        load_and_index(
            self.collection,
            self.patterns,
        )

    def retrieve(self, query, top_k=2):

        return retrieve(
            self.collection,
            query,
            top_k
        )
    


def main():
    print("=" * 60)
    print("Initializing Scam Pattern Knowledge Base...")
    print("=" * 60)

    kb = ScamPatternKB()

    print("\n✅ Knowledge Base initialized successfully!")

    print(f"Loaded Patterns: {len(kb.patterns)}")

    query = "Hello, this is Officer Rajesh from the Cyber Crime Department."

    print("\n" + "=" * 60)
    print("Testing Retrieval")
    print("=" * 60)
    print(f"Query:\n{query}\n")

    results = kb.retrieve(query, top_k=3)

    print("Top Matching Scam Patterns:\n")

    for i, result in enumerate(results, start=1):
        print(f"Result {i}")
        print("-" * 50)
        for key, value in result.items():
            print(f"{key}: {value}")
        print()


if __name__ == "__main__":
    main()
