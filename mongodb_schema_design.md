# MongoDB Collection Design for Listmonk Clone

This document outlines the conceptual schema design for MongoDB collections,
replacing the previous SQL structure.

## General Notes:
- `_id`: MongoDB's default ObjectId, used as the primary key.
- `uuid`: Application-level UUID (string or BSON UUID type) for external referencing.
- `created_at`, `updated_at`: Timestamps for all documents.

## 1. `subscribers` Collection

Stores information about individual subscribers.

**Document Structure:**
```json
{
  "_id": "ObjectId()",
  "uuid": "string (UUID)", // Unique
  "email": "string", // Unique, indexed, store lowercase
  "name": "string",
  "attribs": { // Flexible key-value attributes
    "city": "string",
    "custom_field": "any"
  },
  "status": "string (enabled, disabled, blocklisted)", // Indexed
  "global_blocklisted_reason": "string", // Optional, if globally blocklisted outside of list context
  "created_at": "ISODate()",
  "updated_at": "ISODate()"
}
```

**Key Indexes:**
*   `{ "uuid": 1 }` (unique)
*   `{ "email": 1 }` (unique)
*   `{ "status": 1 }`
*   `{ "created_at": -1 }`

## 2. `mailing_lists` Collection

Defines mailing lists. Subscriber membership will be handled by references or a separate linking collection if complex metadata per subscription is needed (similar to `subscriber_lists` in SQL). For simplicity here, we might start with an array of subscriber `_id`s or `uuid`s if the number of subscribers per list isn't excessively large, or use a dedicated `subscriptions` collection. Given potential scale, a `subscriptions` collection is better.

**Document Structure:**
```json
{
  "_id": "ObjectId()",
  "uuid": "string (UUID)", // Unique
  "name": "string", // Indexed
  "description": "string",
  "type": "string (public, private)", // Corresponds to ListType
  "optin_type": "string (single, double)", // Corresponds to ListOptin
  "tags": ["string"],
  "owner_id": "string (references Django user ID/username, optional)",
  "created_at": "ISODate()",
  "updated_at": "ISODate()"
  // subscriber_count can be maintained here via denormalization or calculated.
}
```

**Key Indexes:**
*   `{ "uuid": 1 }` (unique)
*   `{ "name": 1 }`
*   `{ "type": 1 }`
*   `{ "tags": 1 }` (multikey index)

## 3. `subscriptions` Collection

Manages the many-to-many relationship between subscribers and mailing_lists, including subscription status. This replaces the `subscriber_lists` table.

**Document Structure:**
```json
{
  "_id": "ObjectId()",
  "subscriber_id": "ObjectId()", // Reference to subscribers._id (or subscriber_uuid)
  "list_id": "ObjectId()",       // Reference to mailing_lists._id (or list_uuid)
  "status": "string (unconfirmed, confirmed, unsubscribed)", // Indexed
  "meta": {}, // Any specific metadata about this subscription
  "subscribed_at": "ISODate()", // When subscription was initiated or confirmed
  "unsubscribed_at": "ISODate()", // Optional
  "created_at": "ISODate()",
  "updated_at": "ISODate()"
}
```

**Key Indexes:**
*   `{ "subscriber_id": 1, "list_id": 1 }` (unique, compound)
*   `{ "list_id": 1, "status": 1 }` (for finding confirmed subscribers for a list)
*   `{ "subscriber_id": 1, "status": 1 }`

## 4. `templates` Collection

Stores email templates.

**Document Structure:**
```json
{
  "_id": "ObjectId()",
  "uuid": "string (UUID)", // Unique
  "name": "string",
  "template_type": "string (campaign, campaign_visual, transactional)", // Corresponds to TemplateType
  "subject": "string", // Used for transactional templates primarily
  "body_html": "string", // HTML content
  "body_plain": "string", // Plain text content (optional)
  "body_source": "string", // JSON or source for visual builder
  "is_default": "boolean", // Logic needed to ensure only one default per type
  "created_at": "ISODate()",
  "updated_at": "ISODate()"
}
```
**Key Indexes:**
*   `{ "uuid": 1 }` (unique)
*   `{ "name": 1 }`
*   `{ "template_type": 1, "is_default": 1 }` (though partial unique index for `is_default=true` is tricky)

## 5. `campaigns` Collection

Core collection for campaigns.

**Document Structure:**
```json
{
  "_id": "ObjectId()",
  "uuid": "string (UUID)", // Unique
  "name": "string",
  "subject": "string",
  "from_email": "string",
  "body_html_source": "string", // Raw HTML or reference to builder content
  "body_plain_source": "string", // Raw plain text
  "alt_body_setting": "string (generate, custom)", // How plain text is handled
  "content_type": "string (html, plain, visual, etc.)", // Corresponds to ContentType
  "template_id": "ObjectId()", // Reference to templates._id (or template_uuid) (optional)
  "send_at": "ISODate()", // For scheduled campaigns, indexed
  "status": "string (draft, scheduled, running, paused, cancelled, finished)", // Indexed
  "campaign_type": "string (regular, optin)", // Corresponds to CampaignType
  "tags": ["string"],
  "target_list_ids": ["ObjectId()"], // Array of mailing_lists._id (or list_uuids)
  "segment_query": {}, // For dynamic segments, if implemented (MongoDB query object)

  "created_by_user_id": "string (references Django user ID/username)",
  "created_at": "ISODate()",
  "updated_at": "ISODate()",
  "started_at": "ISODate()", // When sending actually began
  "finished_at": "ISODate()",

  // Statistics (can be updated by Celery tasks, consider if these updates become a bottleneck)
  "stats": {
    "to_send": "number", // Initial count
    "sent": "number",    // Successfully dispatched
    "failed": "number",  // Failed to dispatch
    "views": "number",   // Tracked opens
    "clicks": "number",  // Tracked unique clicks
    "bounces": "number",
    "unsubscribes": "number"
  },

  // Archive settings
  "archive_settings": {
    "is_archived": "boolean",
    "slug": "string", // Unique if archived
    "archive_template_id": "ObjectId()", // Optional
    "meta": {}
  },
  "headers": [{"name": "string", "value": "string"}] // Custom email headers
}
```

**Key Indexes:**
*   `{ "uuid": 1 }` (unique)
*   `{ "status": 1 }`
*   `{ "send_at": 1, "status": 1 }` (for scheduler picking up scheduled campaigns)
*   `{ "tags": 1 }`
*   `{ "created_by_user_id": 1 }`
*   `{ "archive_settings.is_archived": 1, "archive_settings.slug": 1 }` (sparse if slug only exists when archived)

## 6. `tracking_events` Collection

A single collection for high-volume tracking data (views, clicks). This helps in optimizing writes.
Could also be named `analytics_events`.

**Document Structure (Example - can vary based on event type):**
```json
{
  "_id": "ObjectId()",
  "event_type": "string (view, click)", // Indexed
  "campaign_id": "ObjectId()", // Reference to campaigns._id (or campaign_uuid), indexed
  "subscriber_id": "ObjectId()", // Reference to subscribers._id (or subscriber_uuid), indexed
  "timestamp": "ISODate()", // Indexed

  // Click-specific fields
  "link_url": "string", // Original URL for clicks
  "link_uuid_ref": "string (UUID of Link object if maintaining a separate Links collection)",

  // View-specific fields (optional, could include User-Agent, IP if privacy allows)
  "user_agent": "string",
  "ip_address": "string",

  // Common fields
  "processed_for_stats_at": "ISODate()" // To mark if this event has been aggregated into campaign stats
}
```

**Key Indexes:**
*   `{ "campaign_id": 1, "timestamp": -1 }` (for querying events for a campaign)
*   `{ "subscriber_id": 1, "timestamp": -1 }` (for querying events for a subscriber)
*   `{ "event_type": 1, "timestamp": -1 }`
*   `{ "timestamp": 1 }` (for TTL if old raw events are to be expired, or for general time-based queries)
*   `{ "processed_for_stats_at": 1}` (sparse, for finding unprocessed events)

## 7. `bounces` Collection

Stores bounce information.

**Document Structure:**
```json
{
  "_id": "ObjectId()",
  "subscriber_id": "ObjectId()", // Reference to subscribers._id (or subscriber_uuid), indexed
  "campaign_id": "ObjectId()",   // Reference to campaigns._id (or campaign_uuid), (optional, indexed)
  "bounce_type": "string (soft, hard, complaint)", // Corresponds to BounceType, indexed
  "source_type": "string (esp_webhook, mailbox_scan)", // Where bounce info came from
  "raw_bounce_info": {}, // Full bounce message or ESP webhook payload
  "reported_at": "ISODate()", // When the bounce was reported by ESP/source
  "created_at": "ISODate()" // When this record was created in our system
}
```

**Key Indexes:**
*   `{ "subscriber_id": 1, "bounce_type": 1 }`
*   `{ "campaign_id": 1 }`
*   `{ "bounce_type": 1, "reported_at": -1 }`
*   `{ "reported_at": -1 }`

## 8. `media_assets` Collection (Optional, if needed)

If managing media uploads directly.

**Document Structure:**
```json
{
  "_id": "ObjectId()",
  "uuid": "string (UUID)",
  "filename": "string",
  "content_type": "string",
  "storage_provider": "string (filesystem, s3, etc.)",
  "storage_path": "string", // Path or key in the storage provider
  "size_bytes": "number",
  "uploader_user_id": "string",
  "created_at": "ISODate()"
}
```
**Key Indexes:**
*   `{ "uuid": 1 }` (unique)
*   `{ "filename": 1 }`
