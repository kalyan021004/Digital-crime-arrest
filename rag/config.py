import os
from dotenv import load_dotenv

load_dotenv()

DATA_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "data",
    "scam_patterns.json",
)

COLLECTION_NAME = "scam_patterns"

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

# Where the file-backed local Qdrant stores its data when QDRANT_URL is unset.
# Gitignored -- it is a rebuildable artifact, like the old chroma_db/ was.
QDRANT_LOCAL_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "qdrant_data",
)

VECTOR_SIZE = 384