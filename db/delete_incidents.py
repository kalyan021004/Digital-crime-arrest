from db.mongo import incident_collection

result = incident_collection.delete_many({})

print(f"Deleted {result.deleted_count} documents.")