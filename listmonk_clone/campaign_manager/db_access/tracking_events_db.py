# campaign_manager/db_access/tracking_events_db.py
from listmonk_clone.listmonk_clone.mongo_client import get_db
from bson import ObjectId
from datetime import datetime

TRACKING_EVENTS_COLLECTION = "tracking_events"

def _get_collection():
    db = get_db()
    return db[TRACKING_EVENTS_COLLECTION]

def create_view_event(campaign_uuid: str, subscriber_uuid: str, user_agent: str = None, ip_address: str = None) -> dict:
    """Records a campaign view event."""
    coll = _get_collection()
    now = datetime.utcnow()

    # Resolve UUIDs to ObjectIds if campaigns/subscribers collections store them and they are needed for direct linking
    # For simplicity, storing UUIDs directly in the event for now.
    # If using ObjectIds for linking:
    # campaign_obj_id = get_db()["campaigns"].find_one({"uuid": campaign_uuid}, {"_id": 1})
    # subscriber_obj_id = get_db()["subscribers"].find_one({"uuid": subscriber_uuid}, {"_id": 1})
    # if not campaign_obj_id or not subscriber_obj_id:
    #     print(f"Warning: Could not find campaign or subscriber for view event. Camp: {campaign_uuid}, Sub: {subscriber_uuid}")
    #     return None # Or raise error

    event_doc = {
        "event_type": "view",
        "campaign_uuid": campaign_uuid, # Storing app-level UUID
        "subscriber_uuid": subscriber_uuid, # Storing app-level UUID
        # "campaign_id": campaign_obj_id["_id"] if campaign_obj_id else None, # If using ObjectId refs
        # "subscriber_id": subscriber_obj_id["_id"] if subscriber_obj_id else None,
        "timestamp": now,
        "user_agent": user_agent,
        "ip_address": ip_address,
        "processed_for_stats_at": None # Mark as unprocessed
    }
    result = coll.insert_one(event_doc)
    event_doc["_id"] = result.inserted_id
    return event_doc

def create_click_event(campaign_uuid: str, subscriber_uuid: str, link_uuid: str, link_url: str, user_agent: str = None, ip_address: str = None) -> dict:
    """Records a link click event."""
    coll = _get_collection()
    now = datetime.utcnow()

    event_doc = {
        "event_type": "click",
        "campaign_uuid": campaign_uuid,
        "subscriber_uuid": subscriber_uuid,
        "link_uuid_ref": link_uuid, # UUID of the Link document/object
        "link_url": link_url, # Denormalized original URL for convenience
        "timestamp": now,
        "user_agent": user_agent,
        "ip_address": ip_address,
        "processed_for_stats_at": None
    }
    result = coll.insert_one(event_doc)
    event_doc["_id"] = result.inserted_id
    return event_doc

def get_unprocessed_events_for_campaign(campaign_uuid: str, event_type: str, limit: int = 1000):
    """
    Fetches unprocessed tracking events for a campaign to be aggregated into stats.
    """
    coll = _get_collection()
    query = {
        "campaign_uuid": campaign_uuid,
        "event_type": event_type,
        "processed_for_stats_at": None
    }
    return list(coll.find(query).limit(limit))

def mark_events_as_processed(event_ids: list[ObjectId]):
    """
    Marks a list of tracking events (by their _id) as processed for stats.
    """
    coll = _get_collection()
    if not event_ids:
        return 0

    now = datetime.utcnow()
    result = coll.update_many(
        {"_id": {"$in": event_ids}},
        {"$set": {"processed_for_stats_at": now}}
    )
    return result.modified_count

# Add other query functions as needed, e.g., for analytics dashboards
# - Get total views/clicks for a campaign within a time range
# - Get clickthrough rate for links in a campaign
# These would typically use MongoDB's aggregation framework.

def count_campaign_views(campaign_uuid: str) -> int:
    coll = _get_collection()
    return coll.count_documents({"campaign_uuid": campaign_uuid, "event_type": "view"})

def count_campaign_clicks(campaign_uuid: str, link_uuid: str = None) -> int:
    coll = _get_collection()
    query = {"campaign_uuid": campaign_uuid, "event_type": "click"}
    if link_uuid:
        query["link_uuid_ref"] = link_uuid
    return coll.count_documents(query)
