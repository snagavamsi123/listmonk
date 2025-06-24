# campaign_manager/db_access/links_db.py
from listmonk_clone.listmonk_clone.mongo_client import get_db
from bson import ObjectId
import uuid
from datetime import datetime

LINKS_COLLECTION = "links" # As per conceptual schema, if we have a dedicated links collection

def _get_collection():
    db = get_db()
    return db[LINKS_COLLECTION]

def get_or_create_link(url: str) -> tuple[dict, bool]:
    """
    Gets an existing link by URL or creates a new one.
    Returns (link_document, created_boolean).
    """
    coll = _get_collection()
    # Normalize URL? (e.g. remove trailing slash, ensure scheme) - for now, exact match
    link_doc = coll.find_one({"url": url})
    created = False
    if not link_doc:
        now = datetime.utcnow()
        link_doc = {
            "uuid": str(uuid.uuid4()),
            "url": url,
            "created_at": now,
            # "updated_at": now # Not strictly needed if links are immutable post-creation
        }
        result = coll.insert_one(link_doc)
        link_doc["_id"] = result.inserted_id
        created = True
    return link_doc, created

def get_link_by_uuid(link_uuid: str) -> dict | None:
    """Fetches a link by its application UUID."""
    coll = _get_collection()
    return coll.find_one({"uuid": link_uuid})

def get_link_by_id(link_id: str) -> dict | None:
    """Fetches a link by its MongoDB ObjectId string."""
    coll = _get_collection()
    return coll.find_one({"_id": ObjectId(link_id)})

# Other functions as needed, e.g., listing links, although they might not be directly exposed via API.
# Link click counts might be aggregated from tracking_events or denormalized onto the link document itself.
# For example:
# def increment_link_click_count(link_uuid: str):
#     coll = _get_collection()
#     coll.update_one({"uuid": link_uuid}, {"$inc": {"click_count": 1}})
# This would be called after a click is recorded in tracking_events.
