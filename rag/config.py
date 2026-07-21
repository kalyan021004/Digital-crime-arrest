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

VECTOR_SIZE = 384