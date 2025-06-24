# campaign_manager/db_access/campaigns_db.py
from listmonk_clone.listmonk_clone.mongo_client import get_db
from bson import ObjectId
import uuid
from datetime import datetime

CAMPAIGNS_COLLECTION = "campaigns"
TEMPLATES_COLLECTION = "templates" # For resolving template_id
MAILING_LISTS_COLLECTION = "mailing_lists" # For resolving target_list_ids

def _get_collection():
    db = get_db()
    return db[CAMPAIGNS_COLLECTION]

def create_campaign(data: dict) -> dict:
    """
    Creates a new campaign.
    `data` is a dictionary containing campaign fields.
    It should include `name`, `subject`, `from_email`, etc.
    `template_uuid` (optional): application UUID of the template.
    `target_list_uuids` (optional): list of application UUIDs of mailing lists.
    `created_by_user_id` (optional): ID of the user creating campaign.
    """
    coll = _get_collection()
    db = get_db() # For resolving FKs
    now = datetime.utcnow()

    campaign_doc = {
        "uuid": str(uuid.uuid4()),
        "name": data.get("name"),
        "subject": data.get("subject"),
        "from_email": data.get("from_email"),
        "body_html_source": data.get("body_html_source", ""),
        "body_plain_source": data.get("body_plain_source", ""),
        "alt_body_setting": data.get("alt_body_setting", "generate"),
        "content_type": data.get("content_type", "html"), # Validate
        "send_at": data.get("send_at"), # Should be ISODate if provided
        "status": data.get("status", "draft"), # Validate
        "campaign_type": data.get("campaign_type", "regular"), # Validate
        "tags": data.get("tags", []),
        "created_by_user_id": data.get("created_by_user_id"),
        "headers": data.get("headers", []),
        "created_at": now,
        "updated_at": now,
        "stats": { # Initialize stats
            "to_send": 0, "sent": 0, "failed": 0,
            "views": 0, "clicks": 0, "bounces": 0, "unsubscribes": 0
        },
        "archive_settings": data.get("archive_settings", {"is_archived": False})
    }

    # Resolve template_uuid to template_id (ObjectId)
    template_uuid = data.get("template_uuid")
    if template_uuid:
        template_obj = db[TEMPLATES_COLLECTION].find_one({"uuid": template_uuid}, {"_id": 1})
        if template_obj:
            campaign_doc["template_id"] = template_obj["_id"]
        else:
            raise ValueError(f"Template with UUID {template_uuid} not found.")

    # Resolve target_list_uuids to target_list_ids (ObjectIds)
    target_list_uuids = data.get("target_list_uuids", [])
    if target_list_uuids:
        list_object_ids = []
        for l_uuid in target_list_uuids:
            mlist_obj = db[MAILING_LISTS_COLLECTION].find_one({"uuid": l_uuid}, {"_id": 1})
            if mlist_obj:
                list_object_ids.append(mlist_obj["_id"])
            else:
                raise ValueError(f"Mailing list with UUID {l_uuid} not found.")
        campaign_doc["target_list_ids"] = list_object_ids
    else:
        campaign_doc["target_list_ids"] = []

    # Validate required fields
    if not campaign_doc["name"] or not campaign_doc["subject"]:
        raise ValueError("Campaign name and subject are required.")

    result = coll.insert_one(campaign_doc)
    campaign_doc["_id"] = result.inserted_id
    return campaign_doc

def get_campaign_by_id(campaign_id: str) -> dict | None:
    """Fetches a campaign by its MongoDB ObjectId string."""
    coll = _get_collection()
    return coll.find_one({"_id": ObjectId(campaign_id)})

def get_campaign_by_uuid(campaign_uuid: str) -> dict | None:
    """Fetches a campaign by its application UUID."""
    coll = _get_collection()
    # Potentially use an aggregation pipeline to populate template/list names
    return coll.find_one({"uuid": campaign_uuid})


def get_campaigns(query_filter: dict = None, page: int = 1, per_page: int = 20, sort_by: str = "created_at", order: int = -1) -> tuple[list[dict], int]:
    coll = _get_collection()
    if query_filter is None:
        query_filter = {}

    skip_count = (page - 1) * per_page

    # Example of populating referenced data using $lookup (more advanced)
    # This makes the query more complex but can enrich the results directly from DB
    pipeline = [
        {"$match": query_filter},
        {"$sort": {sort_by: order}},
        {"$skip": skip_count},
        {"$limit": per_page},
        # Lookup template name
        {
            "$lookup": {
                "from": TEMPLATES_COLLECTION,
                "localField": "template_id",
                "foreignField": "_id",
                "as": "template_info"
            }
        },
        {"$unwind": {"path": "$template_info", "preserveNullAndEmptyArrays": True}},
        # Lookup list names (more complex for an array of ObjectIds)
        # This would typically involve multiple $lookup and $unwind stages or $addFields with $map
        # For simplicity, this part is often handled application-side for lists of lists.
        # Or, store denormalized list names if performance is critical and updates are managed.
    ]

    # campaigns = list(coll.aggregate(pipeline)) # Use this if doing lookups
    campaigns_cursor = coll.find(query_filter).sort(sort_by, order).skip(skip_count).limit(per_page)
    campaigns = list(campaigns_cursor)

    # Application-side population for referenced data (simpler, but more DB round trips if not careful)
    # db = get_db()
    # for campaign in campaigns:
    #     if campaign.get("template_id"):
    #         template = db[TEMPLATES_COLLECTION].find_one({"_id": campaign["template_id"]}, {"name": 1, "uuid": 1})
    #         campaign["template_info"] = template if template else None
    #     if campaign.get("target_list_ids"):
    #         lists_info = []
    #         for list_id in campaign["target_list_ids"]:
    #             mlist = db[MAILING_LISTS_COLLECTION].find_one({"_id": list_id}, {"name": 1, "uuid": 1})
    #             if mlist: lists_info.append(mlist)
    #         campaign["target_lists_info"] = lists_info


    total_count = coll.count_documents(query_filter)
    return campaigns, total_count

def update_campaign(campaign_uuid: str, update_data: dict) -> int:
    coll = _get_collection()
    db = get_db()
    now = datetime.utcnow()

    update_payload = update_data.copy() # Avoid modifying input dict

    # Resolve template_uuid to template_id if provided
    if "template_uuid" in update_payload:
        template_uuid = update_payload.pop("template_uuid")
        if template_uuid:
            template_obj = db[TEMPLATES_COLLECTION].find_one({"uuid": template_uuid}, {"_id": 1})
            if template_obj:
                update_payload["template_id"] = template_obj["_id"]
            else:
                raise ValueError(f"Template with UUID {template_uuid} not found for update.")
        else: # Clearing template
            update_payload["template_id"] = None

    # Resolve target_list_uuids to target_list_ids if provided
    if "target_list_uuids" in update_payload:
        target_list_uuids = update_payload.pop("target_list_uuids")
        list_object_ids = []
        if target_list_uuids: # Allows clearing lists if empty list is passed
            for l_uuid in target_list_uuids:
                mlist_obj = db[MAILING_LISTS_COLLECTION].find_one({"uuid": l_uuid}, {"_id": 1})
                if mlist_obj:
                    list_object_ids.append(mlist_obj["_id"])
                else:
                    raise ValueError(f"Mailing list with UUID {l_uuid} not found for update.")
        update_payload["target_list_ids"] = list_object_ids


    update_doc = {"$set": update_payload}
    if "$set" not in update_payload and any(op.startswith('$') for op in update_payload.keys()): # if already using operators
        update_doc = update_payload
    else: # Default to $set if no operators
        update_doc = {"$set": update_payload}

    if "$set" not in update_doc: # ensure $set exists if it was just update_payload
        update_doc["$set"] = {}
    update_doc["$set"]["updated_at"] = now

    result = coll.update_one({"uuid": campaign_uuid}, update_doc)
    return result.modified_count

def delete_campaign(campaign_uuid: str) -> int:
    coll = _get_collection()
    # TODO: Consider related data: tracking_events, bounces associated with this campaign.
    # These might be kept for historical reasons or cleaned up by separate archival/cleanup tasks.
    result = coll.delete_one({"uuid": campaign_uuid})
    return result.deleted_count

def update_campaign_status(campaign_uuid: str, new_status: str) -> int:
    coll = _get_collection()
    now = datetime.utcnow()
    update_fields = {"status": new_status, "updated_at": now}
    if new_status == "running": # Assuming 'running' is the value from CampaignStatus enum
        update_fields["started_at"] = now # Set started_at when campaign starts running
    elif new_status == "finished": # Assuming 'finished' is the value from CampaignStatus enum
        update_fields["finished_at"] = now

    result = coll.update_one({"uuid": campaign_uuid}, {"$set": update_fields})
    return result.modified_count

def update_campaign_stats(campaign_uuid: str, stats_update: dict) -> int:
    """
    Updates fields within the 'stats' subdocument of a campaign.
    `stats_update` should be like `{"stats.sent": 1, "stats.views": 5}` for $inc
    or `{"stats.to_send": 100}` for $set.
    This function expects the caller to use MongoDB update operators like $inc.
    """
    coll = _get_collection()

    update_doc = {}
    for key, value in stats_update.items():
        if key.startswith("stats.") and isinstance(value, dict) and any(op.startswith('$') for op in value.keys()):
            # If value is already an operator dict like {"$inc": 1}
             if key not in update_doc: update_doc[key] = {} # Should not happen if key is unique
             for op, op_val in value.items():
                 update_doc.setdefault(op, {})[key] = op_val # e.g. {"$inc": {"stats.sent": 1}}
        elif key.startswith("stats."): # Direct set of a stat field
            update_doc.setdefault("$set", {})[key] = value
        else: # Assume it's an increment if not specified with operator and is a number
            if isinstance(value, (int, float)):
                 update_doc.setdefault("$inc", {})[f"stats.{key}"] = value
            else: # set if not a number
                update_doc.setdefault("$set", {})[f"stats.{key}"] = value


    if not update_doc: # No valid stat updates
        return 0

    if "$set" not in update_doc: update_doc["$set"] = {}
    update_doc["$set"]["updated_at"] = datetime.utcnow()

    result = coll.update_one({"uuid": campaign_uuid}, update_doc)
    return result.modified_count


def get_campaigns_for_sending(target_datetime: datetime) -> list[dict]:
    """ Fetches campaigns that are scheduled to be sent or are currently running. """
    coll = _get_collection()
    query = {
        "$or": [
            {"status": "scheduled", "send_at": {"$lte": target_datetime}},
            {"status": "running"} # For campaigns that might have been interrupted
        ]
    }
    return list(coll.find(query))
