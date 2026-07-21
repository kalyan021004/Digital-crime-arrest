"""
MongoDB connection with a safe in-memory fallback.

Why the fallback: the demo pipeline must not die because a database is
offline. Previously, if the connection failed we printed an error but never
assigned `incident_collection`, so every downstream
`from db.mongo import incident_collection` raised ImportError and the whole
application refused to start. A dropped Mongo connection took down scam
detection, which is exactly backwards -- detection is the critical path,
persistence is not.

Now: if Mongo is unreachable we fall back to an in-memory store that
implements the small subset of the collection API this project uses. The
pipeline keeps running and warns loudly that incidents are not being
persisted.
"""

import os

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")

DB_NAME = "digital_arrest_shield"

# Single source of truth for the collection name. Previously db/mongo.py wrote
# to "incident_reports" while geospatial/crime_intelligence.py read from
# "incidents", so geospatial queries silently always returned empty.
INCIDENT_COLLECTION_NAME = "incident_reports"


class InMemoryCollection:
    """
    Minimal stand-in for a pymongo Collection.

    Implements only what this codebase actually calls: update_one(upsert=True),
    find(), count_documents() and delete_many(). It is deliberately simple --
    enough to keep a demo running, not a Mongo emulator.
    """

    def __init__(self):
        self._docs = {}
        self._auto_id = 0

    def update_one(self, filt, update, upsert=False):
        key = filt.get("session_id")
        if key is None:
            self._auto_id += 1
            key = f"_auto_{self._auto_id}"

        new_values = update.get("$set", {})

        if key in self._docs:
            self._docs[key].update(new_values)
        elif upsert:
            doc = {"session_id": key}
            doc.update(new_values)
            self._docs[key] = doc

        return None

    def find(self, filt=None):
        docs = list(self._docs.values())
        if not filt:
            return iter(docs)
        return iter(
            [d for d in docs if all(d.get(k) == v for k, v in filt.items())]
        )

    def count_documents(self, filt=None):
        return len(list(self.find(filt)))

    def delete_many(self, filt=None):
        removed = len(list(self.find(filt)))
        if not filt:
            self._docs.clear()
        else:
            for d in list(self.find(filt)):
                self._docs.pop(d.get("session_id"), None)

        class _Result:
            deleted_count = removed

        return _Result()


def _connect():
    """Try Mongo; fall back to in-memory. Always returns a usable collection."""
    try:
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        print("[db] Connected to MongoDB")
        return client[DB_NAME][INCIDENT_COLLECTION_NAME], True
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        print("[db] WARNING: MongoDB unreachable -- using in-memory store.")
        print(f"[db] Incidents will NOT be persisted. Reason: {exc}")
        return InMemoryCollection(), False


incident_collection, MONGO_AVAILABLE = _connect()
