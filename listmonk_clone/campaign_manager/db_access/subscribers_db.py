# campaign_manager/db_access/subscribers_db.py
from listmonk_clone.listmonk_clone.mongo_client import get_db
from bson import ObjectId
import uuid
from datetime import datetime

SUBSCRIBERS_COLLECTION = "subscribers"

def _get_collection():
    db = get_db()
    return db[SUBSCRIBERS_COLLECTION]

def create_subscriber(email: str, name: str, attribs: dict = None, status: str = "enabled") -> dict:
    """
    Creates a new subscriber.
    Returns the inserted document including its _id.
    """
    coll = _get_collection()
    now = datetime.utcnow()
    subscriber_doc = {
        "uuid": str(uuid.uuid4()),
        "email": email.lower(),
        "name": name,
        "attribs": attribs if attribs is not None else {},
        "status": status, # Add validation against SubscriberStatus enum if needed
        "created_at": now,
        "updated_at": now
    }
    # Ensure email is unique before inserting
    if coll.find_one({"email": subscriber_doc["email"]}):
        raise ValueError(f"Subscriber with email {subscriber_doc['email']} already exists.")

    result = coll.insert_one(subscriber_doc)
    subscriber_doc["_id"] = result.inserted_id
    return subscriber_doc

def get_subscriber_by_id(subscriber_id: str) -> dict | None:
    """Fetches a subscriber by its MongoDB ObjectId string."""
    coll = _get_collection()
    return coll.find_one({"_id": ObjectId(subscriber_id)})

def get_subscriber_by_uuid(subscriber_uuid: str) -> dict | None:
    """Fetches a subscriber by its application UUID."""
    coll = _get_collection()
    return coll.find_one({"uuid": subscriber_uuid})

def get_subscriber_by_email(email: str) -> dict | None:
    """Fetches a subscriber by email."""
    coll = _get_collection()
    return coll.find_one({"email": email.lower()})

def get_subscribers(query_filter: dict = None, page: int = 1, per_page: int = 20, sort_by: str = "created_at", order: int = -1) -> tuple[list[dict], int]:
    """
    Fetches subscribers with pagination and sorting.
    `query_filter` is a MongoDB query document.
    `order` is 1 for ascending, -1 for descending.
    Returns a tuple of (list of subscribers, total_count).
    """
    coll = _get_collection()
    if query_filter is None:
        query_filter = {}

    skip_count = (page - 1) * per_page
    cursor = coll.find(query_filter).sort(sort_by, order).skip(skip_count).limit(per_page)
    subscribers = list(cursor)
    total_count = coll.count_documents(query_filter)
    return subscribers, total_count

def update_subscriber(subscriber_uuid: str, update_data: dict) -> int:
    """
    Updates a subscriber identified by UUID.
    `update_data` should be a dict of fields to update.
    Returns the number of documents modified (0 or 1).
    """
    coll = _get_collection()

    # Ensure email uniqueness if it's being updated
    if "email" in update_data:
        existing_sub = coll.find_one({"email": update_data["email"].lower(), "uuid": {"$ne": subscriber_uuid}})
        if existing_sub:
            raise ValueError(f"Another subscriber with email {update_data['email']} already exists.")
        update_data["email"] = update_data["email"].lower()

    update_doc = {"$set": update_data}
    if "$set" not in update_data: # If raw update_data is passed without $set
         update_doc = {"$set": update_data}
    else: # if update_data already has operators like $set, $unset
        update_doc = update_data

    update_doc["$set"]["updated_at"] = datetime.utcnow() # Always update this

    result = coll.update_one({"uuid": subscriber_uuid}, update_doc)
    return result.modified_count

def delete_subscriber(subscriber_uuid: str) -> int:
    """
    Deletes a subscriber by UUID.
    Returns the number of documents deleted (0 or 1).
    """
    coll = _get_collection()
    # TODO: Consider implications: what happens to their subscriptions?
    # This might need to also trigger deletion from the 'subscriptions' collection.
    # For now, just deleting the subscriber document.
    result = coll.delete_one({"uuid": subscriber_uuid})
    return result.deleted_count

def blocklist_subscribers_by_ids(subscriber_uuids: list[str]) -> int:
    """Blocklists multiple subscribers by their UUIDs."""
    coll = _get_collection()
    result = coll.update_many(
        {"uuid": {"$in": subscriber_uuids}},
        {"$set": {"status": "blocklisted", "updated_at": datetime.utcnow()}}
    )
    return result.modified_count

# Add more specific query functions as needed, e.g.,
# def find_subscribers_by_status(status: str): ...
# def search_subscribers_by_attribs(key: str, value: any): ...
