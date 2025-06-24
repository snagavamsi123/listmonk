# campaign_manager/db_access/mailing_lists_db.py
from listmonk_clone.listmonk_clone.mongo_client import get_db
from bson import ObjectId
import uuid
from datetime import datetime

MAILING_LISTS_COLLECTION = "mailing_lists"
SUBSCRIPTIONS_COLLECTION = "subscriptions" # Needed for subscriber_count

def _get_collection():
    db = get_db()
    return db[MAILING_LISTS_COLLECTION]

def _get_subscriptions_collection():
    db = get_db()
    return db[SUBSCRIPTIONS_COLLECTION]

def create_mailing_list(name: str, list_type: str, optin_type: str, description: str = "", tags: list = None) -> dict:
    """
    Creates a new mailing list.
    Returns the inserted document.
    """
    coll = _get_collection()
    now = datetime.utcnow()
    list_doc = {
        "uuid": str(uuid.uuid4()),
        "name": name,
        "description": description,
        "type": list_type, # Validate against ListType enum if needed
        "optin_type": optin_type, # Validate against ListOptin enum
        "tags": tags if tags is not None else [],
        "created_at": now,
        "updated_at": now,
        "subscriber_count": 0 # Initialize, actual count might be managed by other operations or tasks
    }
    # Optional: Check for unique name if required by business logic
    # if coll.find_one({"name": name}):
    #     raise ValueError(f"Mailing list with name {name} already exists.")

    result = coll.insert_one(list_doc)
    list_doc["_id"] = result.inserted_id
    return list_doc

def get_mailing_list_by_id(list_id: str) -> dict | None:
    """Fetches a mailing list by its MongoDB ObjectId string."""
    coll = _get_collection()
    return coll.find_one({"_id": ObjectId(list_id)})

def get_mailing_list_by_uuid(list_uuid: str) -> dict | None:
    """Fetches a mailing list by its application UUID."""
    coll = _get_collection()
    return coll.find_one({"uuid": list_uuid})

def get_mailing_lists(query_filter: dict = None, page: int = 1, per_page: int = 20, sort_by: str = "name", order: int = 1) -> tuple[list[dict], int]:
    """
    Fetches mailing lists with pagination, sorting, and an attempt to get subscriber_count.
    `query_filter` is a MongoDB query document.
    `order` is 1 for ascending, -1 for descending.
    Returns a tuple of (list of mailing_lists, total_count).
    Note: Getting accurate real-time subscriber_count for each list can be intensive.
          This example does a basic count. For performance, this might be denormalized
          and updated periodically or upon subscription changes.
    """
    coll = _get_collection()
    subs_coll = _get_subscriptions_collection()

    if query_filter is None:
        query_filter = {}

    skip_count = (page - 1) * per_page
    cursor = coll.find(query_filter).sort(sort_by, order).skip(skip_count).limit(per_page)

    mailing_lists = []
    for mlist in cursor:
        # Get subscriber count for this list (example: confirmed subscribers)
        # This is N+1 query pattern if done per list here. Consider aggregation pipeline for larger scale.
        # Or, if subscriber_count is denormalized on the mailing_list document:
        # mlist['subscriber_count'] = mlist.get('subscriber_count', 0)

        # Example of fetching live count (can be slow for many lists)
        count = subs_coll.count_documents({
            "list_id": mlist["_id"], # Assuming list_id in subscriptions stores ObjectId of mailing_list
            "status": "confirmed" # Example: count only confirmed subscribers
        })
        mlist['subscriber_count'] = count
        mailing_lists.append(mlist)

    total_count = coll.count_documents(query_filter)
    return mailing_lists, total_count

def get_public_mailing_lists() -> list[dict]:
    """Fetches public mailing lists (name and uuid only)."""
    coll = _get_collection()
    cursor = coll.find({"type": "public"}, {"uuid": 1, "name": 1, "_id": 0}) # Projection
    return list(cursor)


def update_mailing_list(list_uuid: str, update_data: dict) -> int:
    """
    Updates a mailing list identified by UUID.
    Returns the number of documents modified.
    """
    coll = _get_collection()
    update_doc = {"$set": update_data}
    if "$set" not in update_data:
         update_doc = {"$set": update_data}
    else:
        update_doc = update_data

    update_doc["$set"]["updated_at"] = datetime.utcnow()

    result = coll.update_one({"uuid": list_uuid}, update_doc)
    return result.modified_count

def delete_mailing_list(list_uuid: str) -> int:
    """
    Deletes a mailing list by UUID.
    Also needs to handle related subscriptions.
    Returns the number of documents deleted from mailing_lists collection.
    """
    coll = _get_collection()
    subs_coll = _get_subscriptions_collection()

    # Get the list's ObjectId before deleting, to remove subscriptions
    list_to_delete = coll.find_one({"uuid": list_uuid}, {"_id": 1})
    if not list_to_delete:
        return 0

    list_object_id = list_to_delete["_id"]

    # Delete the list
    delete_result = coll.delete_one({"uuid": list_uuid})

    if delete_result.deleted_count > 0:
        # Delete related subscriptions
        subs_delete_result = subs_coll.delete_many({"list_id": list_object_id})
        print(f"Deleted {subs_delete_result.deleted_count} subscriptions for list UUID {list_uuid}")
        # TODO: Consider impact on campaigns that might target this list.
        # Listmonk SQL schema sets list_id to NULL in campaign_lists.
        # Here, we might need to update campaign documents to remove this list_id from `target_list_ids`.
        # This requires careful cascading logic or denormalization choices.

    return delete_result.deleted_count

def update_subscriber_count(list_uuid: str, count_change: int):
    """
    Helper to denormalize subscriber_count on a mailing list.
    `count_change` can be positive (for new sub) or negative (for unsub).
    This should be called carefully within transactions if possible, or by reliable tasks.
    """
    coll = _get_collection()
    coll.update_one(
        {"uuid": list_uuid},
        {"$inc": {"subscriber_count": count_change}, "$set": {"updated_at": datetime.utcnow()}}
    )

# TODO:
# Functions for managing subscriptions (add subscriber to list, remove, change status)
# will likely go into a `subscriptions_db.py` file, as they interact with the
# `subscriptions` collection primarily, linking subscribers and lists.
# Example:
# def add_subscriber_to_list(subscriber_id_obj, list_id_obj, status): ...
# def remove_subscriber_from_list(subscriber_id_obj, list_id_obj): ...
# def get_subscriptions_for_subscriber(subscriber_id_obj): ...
# def get_subscribers_for_list(list_id_obj, status_filter=None): ...
