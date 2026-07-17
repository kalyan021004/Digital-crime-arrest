import json
from .config import DATA_PATH

def load_patterns():
    with open(DATA_PATH, "r") as f:
        return json.load(f)