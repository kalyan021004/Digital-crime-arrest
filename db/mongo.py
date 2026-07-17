from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")

try:
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)

    # Verify the connection
    client.admin.command("ping")
    print("✅ Connected to MongoDB")

    db = client["digital_arrest_shield"]
    incident_collection = db["incident_reports"]

except ConnectionFailure as e:
    print("❌ Failed to connect to MongoDB")
    print(e) 