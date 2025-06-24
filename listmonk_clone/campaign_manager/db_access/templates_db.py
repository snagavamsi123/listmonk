# campaign_manager/db_access/templates_db.py
from listmonk_clone.listmonk_clone.mongo_client import get_db
from bson import ObjectId
import uuid
from datetime import datetime

TEMPLATES_COLLECTION = "templates"

def _get_collection():
    db = get_db()
    return db[TEMPLATES_COLLECTION]

def create_template(name: str, template_type: str, body_html: str, subject: str = "",
                    body_plain: str = None, body_source: str = None, is_default: bool = False) -> dict:
    coll = _get_collection()
    now = datetime.utcnow()

    # If setting this as default, ensure no other template of the same type is default.
    # This logic should ideally be atomic or handled carefully.
    if is_default:
        coll.update_many(
            {"template_type": template_type, "is_default": True},
            {"$set": {"is_default": False, "updated_at": now}}
        )

    template_doc = {
        "uuid": str(uuid.uuid4()),
        "name": name,
        "template_type": template_type, # Validate against TemplateType enum
        "subject": subject,
        "body_html": body_html,
        "body_plain": body_plain,
        "body_source": body_source, # For visual builder
        "is_default": is_default,
        "created_at": now,
        "updated_at": now
    }
    result = coll.insert_one(template_doc)
    template_doc["_id"] = result.inserted_id
    return template_doc

def get_template_by_id(template_id: str) -> dict | None:
    coll = _get_collection()
    return coll.find_one({"_id": ObjectId(template_id)})

def get_template_by_uuid(template_uuid: str) -> dict | None:
    coll = _get_collection()
    return coll.find_one({"uuid": template_uuid})

def get_templates(query_filter: dict = None, page: int = 1, per_page: int = 20, sort_by: str = "name", order: int = 1) -> tuple[list[dict], int]:
    coll = _get_collection()
    if query_filter is None:
        query_filter = {}

    skip_count = (page - 1) * per_page
    cursor = coll.find(query_filter).sort(sort_by, order).skip(skip_count).limit(per_page)
    templates = list(cursor)
    total_count = coll.count_documents(query_filter)
    return templates, total_count

def get_default_template(template_type: str) -> dict | None:
    coll = _get_collection()
    return coll.find_one({"template_type": template_type, "is_default": True})

def update_template(template_uuid: str, update_data: dict) -> int:
    coll = _get_collection()
    now = datetime.utcnow()

    # Handle is_default logic if it's being changed
    if update_data.get("is_default") is True:
        current_template = coll.find_one({"uuid": template_uuid}, {"template_type": 1})
        if current_template:
            coll.update_many(
                {"template_type": current_template["template_type"], "is_default": True, "uuid": {"$ne": template_uuid}},
                {"$set": {"is_default": False, "updated_at": now}}
            )

    update_doc = {"$set": update_data}
    if "$set" not in update_data:
         update_doc = {"$set": update_data}
    else:
        update_doc = update_data

    update_doc["$set"]["updated_at"] = now

    result = coll.update_one({"uuid": template_uuid}, update_doc)
    return result.modified_count

def set_template_as_default(template_uuid: str) -> bool:
    coll = _get_collection()
    now = datetime.utcnow()
    template = coll.find_one({"uuid": template_uuid})
    if not template:
        return False

    # Unset other defaults of the same type
    coll.update_many(
        {"template_type": template["template_type"], "is_default": True, "uuid": {"$ne": template_uuid}},
        {"$set": {"is_default": False, "updated_at": now}}
    )
    # Set this one as default
    result = coll.update_one(
        {"uuid": template_uuid},
        {"$set": {"is_default": True, "updated_at": now}}
    )
    return result.modified_count > 0

def delete_template(template_uuid: str) -> int:
    coll = _get_collection()
    # TODO: Check if this template is used by any campaigns or archive settings.
    # Listmonk's SQL schema uses ON DELETE SET NULL for template_id in campaigns.
    # For MongoDB, this would require finding campaigns using this template's ObjectId
    # and unsetting their template_id or setting it to a default.
    # This is complex application-level cascading. For now, direct delete.
    # campaign_coll = get_db()["campaigns"]
    # template_obj_id = coll.find_one({"uuid": template_uuid}, {"_id": 1})
    # if template_obj_id:
    #    campaign_coll.update_many({"template_id": template_obj_id["_id"]}, {"$set": {"template_id": None, "updated_at": now}})
    #    campaign_coll.update_many({"archive_settings.archive_template_id": template_obj_id["_id"]}, {"$set": {"archive_settings.archive_template_id": None, "updated_at": now}})

    result = coll.delete_one({"uuid": template_uuid})
    return result.deleted_count
