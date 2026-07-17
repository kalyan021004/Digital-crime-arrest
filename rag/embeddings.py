from chromadb import EmbeddingFunction
from chromadb import Documents, Embeddings
from sentence_transformers import SentenceTransformer
import numpy as np


class SentenceTransformerEmbeddingFunction(EmbeddingFunction):

    def __init__(self,
                 model_name="BAAI/bge-small-en-v1.5"):

        self.model = SentenceTransformer(model_name)

    def __call__(self, input: Documents) -> Embeddings:

        embeddings = self.model.encode(
            input,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False
        )

        return embeddings.astype(np.float32).tolist()