# campaign_manager/db_access/subscriptions_db.py
from listmonk_clone.listmonk_clone.mongo_client import get_db
from bson import ObjectId
from datetime import datetime

SUBSCRIPTIONS_COLLECTION = "subscriptions"
# Assuming SubscriberStatus and SubscriptionStatus enums are defined elsewhere or use strings directly
# For this DAL, we'll use strings and expect validation at a higher level (e.g., views/serializers)

def _get_collection():
    db = get_db()
    return db[SUBSCRIPTIONS_COLLECTION]

def add_subscription(subscriber_object_id: ObjectId, list_object_id: ObjectId, status: str, meta: dict = None) -> dict:
    """
    Adds or updates a subscription for a subscriber to a mailing list.
    Uses subscriber and list ObjectIds.
    """
    coll = _get_collection()
    now = datetime.utcnow()

    # Check if subscription already exists
    existing_subscription = coll.find_one({
        "subscriber_id": subscriber_object_id,
        "list_id": list_object_id
    })

    if existing_subscription:
        # Update existing subscription if status or meta changes
        update_fields = {}
        if existing_subscription.get("status") != status:
            update_fields["status"] = status
        if meta is not None and existing_subscription.get("meta") != meta:
            update_fields["meta"] = meta

        if update_fields:
            update_fields["updated_at"] = now
            coll.update_one(
                {"_id": existing_subscription["_id"]},
                {"$set": update_fields}
            )
            # Fetch and return the updated document
            return coll.find_one({"_id": existing_subscription["_id"]})
        return existing_subscription # No changes needed
    else:
        # Create new subscription
        subscription_doc = {
            "subscriber_id": subscriber_object_id,
            "list_id": list_object_id,
            "status": status,
            "meta": meta if meta is not None else {},
            "subscribed_at": now, # Could be different based on confirmation flow
            "created_at": now,
            "updated_at": now
        }
        result = coll.insert_one(subscription_doc)
        subscription_doc["_id"] = result.inserted_id

        # TODO: Potentially update mailing_list.subscriber_count here or via a task
        # from .mailing_lists_db import update_subscriber_count # Be careful with circular imports
        # if status == "confirmed":
        #    update_subscriber_count_by_list_obj_id(list_object_id, 1)
        return subscription_doc


def get_subscription(subscriber_object_id: ObjectId, list_object_id: ObjectId) -> dict | None:
    coll = _get_collection()
    return coll.find_one({
        "subscriber_id": subscriber_object_id,
        "list_id": list_object_id
    })

def update_subscription_status(subscriber_object_id: ObjectId, list_object_id: ObjectId, new_status: str) -> int:
    coll = _get_collection()
    now = datetime.utcnow()
    update_doc = {"$set": {"status": new_status, "updated_at": now}}
    if new_status == "unsubscribed":
        update_doc["$set"]["unsubscribed_at"] = now

    result = coll.update_one(
        {"subscriber_id": subscriber_object_id, "list_id": list_object_id},
        update_doc
    )
    # TODO: Update mailing_list.subscriber_count accordingly
    return result.modified_count

def remove_subscription(subscriber_object_id: ObjectId, list_object_id: ObjectId) -> int:
    coll = _get_collection()
    result = coll.delete_one({
        "subscriber_id": subscriber_object_id,
        "list_id": list_object_id
    })
    # TODO: Decrement mailing_list.subscriber_count if subscription was confirmed
    return result.deleted_count

def get_subscriptions_for_subscriber(subscriber_object_id: ObjectId, status_filter: str = None) -> list[dict]:
    coll = _get_collection()
    query = {"subscriber_id": subscriber_object_id}
    if status_filter:
        query["status"] = status_filter

    # We might want to populate list information here using an aggregation pipeline
    # For now, just returning the subscription documents
    return list(coll.find(query))


def get_subscribers_for_list(list_object_id: ObjectId, status_filter: str = None, page: int = 1, per_page: int = 1000) -> tuple[list[ObjectId], int]:
    """
    Fetches subscriber ObjectIds for a given list, with optional status filter and pagination.
    Returns a list of subscriber_ids (ObjectId) and total count.
    This is optimized to fetch only IDs for further processing (e.g., campaign sending).
    """
    coll = _get_collection()
    query = {"list_id": list_object_id}
    if status_filter:
        query["status"] = status_filter

    skip_count = (page - 1) * per_page
    cursor = coll.find(query, {"subscriber_id": 1, "_id": 0}).skip(skip_count).limit(per_page)

    subscriber_ids = [doc["subscriber_id"] for doc in cursor]
    total_count = coll.count_documents(query)

    return subscriber_ids, total_count

def count_subscribers_for_list(list_object_id: ObjectId, status_filter: str = "confirmed") -> int:
    """Counts subscribers for a list with a given status."""
    coll = _get_collection()
    query = {"list_id": list_object_id}
    if status_filter:
        query["status"] = status_filter
    return coll.count_documents(query)

# Helper to be called by mailing_lists_db or tasks to avoid circular import issues at module level
def update_subscriber_count_by_list_obj_id(list_object_id: ObjectId, change: int):
    # This is a conceptual placement. The actual update_subscriber_count on mailing_list
    # might be better handled by a task that listens to subscription events or
    # directly in the mailing_lists_db if circular imports are managed (e.g. by importing at method level)
    # For now, this illustrates where the call to update the denormalized count would originate.
    from .mailing_lists_db import _get_collection as get_ml_coll # Local import
    ml_coll = get_ml_coll()
    ml_coll.update_one(
        {"_id": list_object_id},
        {"$inc": {"subscriber_count": change}, "$set": {"updated_at": datetime.utcnow()}}
    )
    print(f"Updated subscriber count for list {list_object_id} by {change}")

# More complex queries, e.g., bulk changing subscription status for many subscribers on a list:
def bulk_update_subscription_status_for_list(list_object_id: ObjectId, subscriber_object_ids: list[ObjectId], new_status: str) -> int:
    coll = _get_collection()
    now = datetime.utcnow()
    update_doc = {"$set": {"status": new_status, "updated_at": now}}
    if new_status == "unsubscribed":
        update_doc["$set"]["unsubscribed_at"] = now

    result = coll.update_many(
        {"list_id": list_object_id, "subscriber_id": {"$in": subscriber_object_ids}},
        update_doc
    )
    # TODO: Update mailing_list.subscriber_count (this is complex as it depends on old vs new status for each sub)
    return result.modified_count
