# listmonk_clone/mongo_client.py
from pymongo import MongoClient
from django.conf import settings

_mongo_client = None
_db = None

def get_mongo_client():
    global _mongo_client
    if _mongo_client is None:
        try:
            mongo_uri = getattr(settings, 'MONGO_URI', 'mongodb://localhost:27017/')
            _mongo_client = MongoClient(mongo_uri)
            # You can add server selection timeout or other client options here
            _mongo_client.admin.command('ping') # Verify connection
            print("Successfully connected to MongoDB.")
        except Exception as e:
            print(f"Error connecting to MongoDB: {e}")
            # Handle connection error appropriately - maybe raise an exception
            # or return None, depending on how you want your app to behave on DB failure.
            raise ConnectionError(f"Could not connect to MongoDB: {e}") from e
    return _mongo_client

def get_db():
    global _db
    if _db is None:
        client = get_mongo_client()
        if client:
            db_name = getattr(settings, 'MONGO_DB_NAME', 'listmonk_mongo_db')
            _db = client[db_name]
        else:
            # This case should ideally not be reached if get_mongo_client() raises an error on failure
            raise ConnectionError("MongoDB client not available, cannot get database.")
    return _db

# Example of how to get a specific collection:
# def get_subscribers_collection():
#     db = get_db()
#     return db["subscribers"]

# It's often better to get the db object and then access collections in your DAL,
# e.g., db = get_db(); db.subscribers.find_one(...)
# This makes the client utility more generic.

# Optional: Close client on application shutdown (more relevant for specific app server setups)
# import atexit
# def close_mongo_client():
#     global _mongo_client
#     if _mongo_client:
#         _mongo_client.close()
#         print("MongoDB connection closed.")
# atexit.register(close_mongo_client)

# Note: For Django, managing client lifecycle might be better handled
# with signals (e.g., `connection_created` for some DBs, though not directly for Mongo).
# For many web apps, creating the client once per process (as this global pattern does)
# and letting the driver manage the connection pool is sufficient.
# Ensure your MongoDB server is configured for adequate connections.
