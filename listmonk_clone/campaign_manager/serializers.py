# campaign_manager/serializers.py
from rest_framework import serializers
from bson import ObjectId # For validating ObjectIds if they are part of API path or payload

# --- Helper to convert MongoDB ObjectId to string for responses ---
class ObjectIdField(serializers.Field):
    def to_representation(self, value):
        if isinstance(value, ObjectId):
            return str(value)
        return value # Keep as is if already string or other type

    def to_internal_value(self, data):
        try:
            return ObjectId(data)
        except Exception:
            raise serializers.ValidationError("Invalid ObjectId.")

# --- Subscriber Serializers ---
class SubscriberAttribsSerializer(serializers.Serializer): # For nested attribs
    # Define fields if you want specific validation, otherwise it's a dict
    # Example: city = serializers.CharField(required=False)
    class Meta:
        extra_kwargs = {'additional_properties': True} # Allow any fields

class SubscriberInputSerializer(serializers.Serializer):
    email = serializers.EmailField()
    name = serializers.CharField(max_length=200)
    attribs = serializers.JSONField(required=False, default=dict) # Using JSONField for flexible dict
    status = serializers.ChoiceField(choices=["enabled", "disabled", "blocklisted"], default="enabled")

class SubscriberOutputSerializer(SubscriberInputSerializer):
    _id = ObjectIdField(read_only=True)
    uuid = serializers.UUIDField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    # Add any other fields that are returned by the DAL but not in input

# --- Mailing List Serializers ---
class MailingListInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    type = serializers.ChoiceField(choices=["public", "private"])
    optin_type = serializers.ChoiceField(choices=["single", "double"])
    tags = serializers.ListField(child=serializers.CharField(max_length=100), required=False, default=list)

class MailingListOutputSerializer(MailingListInputSerializer):
    _id = ObjectIdField(read_only=True)
    uuid = serializers.UUIDField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    subscriber_count = serializers.IntegerField(read_only=True, required=False, default=0)

class PublicMailingListOutputSerializer(serializers.Serializer): # For the public lists endpoint
    uuid = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)


# --- Subscription Serializers ---
class SubscriptionInputSerializer(serializers.Serializer):
    # Usually created via specific actions, not a generic CRUD on subscriptions directly by client
    # subscriber_uuid = serializers.UUIDField() # Or use ObjectIds if API exposes them
    # list_uuid = serializers.UUIDField()
    status = serializers.ChoiceField(choices=["unconfirmed", "confirmed", "unsubscribed"])
    meta = serializers.JSONField(required=False, default=dict)

class SubscriptionOutputSerializer(SubscriptionInputSerializer):
    _id = ObjectIdField(read_only=True)
    subscriber_id = ObjectIdField() # Represents ObjectId from DB
    list_id = ObjectIdField()       # Represents ObjectId from DB
    subscribed_at = serializers.DateTimeField(read_only=True, required=False)
    unsubscribed_at = serializers.DateTimeField(read_only=True, required=False, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    # Potentially include subscriber email/name and list name for richer output
    # subscriber_email = serializers.EmailField(source='subscriber.email', read_only=True) # If DAL populates this
    # list_name = serializers.CharField(source='list.name', read_only=True)


# --- Template Serializers ---
class TemplateInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    template_type = serializers.ChoiceField(choices=["campaign", "campaign_visual", "transactional"])
    subject = serializers.CharField(required=False, allow_blank=True, default="") # Required for 'tx' type typically
    body_html = serializers.CharField()
    body_plain = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    body_source = serializers.CharField(required=False, allow_blank=True, allow_null=True) # For visual builder
    is_default = serializers.BooleanField(default=False)

class TemplateOutputSerializer(TemplateInputSerializer):
    _id = ObjectIdField(read_only=True)
    uuid = serializers.UUIDField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


# --- Campaign Serializers ---
class CampaignStatSerializer(serializers.Serializer):
    to_send = serializers.IntegerField(default=0)
    sent = serializers.IntegerField(default=0)
    failed = serializers.IntegerField(default=0)
    views = serializers.IntegerField(default=0)
    clicks = serializers.IntegerField(default=0)
    bounces = serializers.IntegerField(default=0)
    unsubscribes = serializers.IntegerField(default=0)

class CampaignArchiveSettingsSerializer(serializers.Serializer):
    is_archived = serializers.BooleanField(default=False)
    slug = serializers.SlugField(required=False, allow_blank=True, allow_null=True)
    archive_template_uuid = serializers.UUIDField(required=False, allow_null=True) # Changed from _id for API layer
    meta = serializers.JSONField(required=False, default=dict)


class CampaignHeaderSerializer(serializers.Serializer):
    name = serializers.CharField()
    value = serializers.CharField()

class CampaignInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    subject = serializers.CharField(max_length=255)
    from_email = serializers.EmailField()
    body_html_source = serializers.CharField(allow_blank=True, default="")
    body_plain_source = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    # alt_body_setting = serializers.ChoiceField(choices=["generate", "custom"], default="generate") # If this is a feature
    content_type = serializers.ChoiceField(choices=["html", "plain", "visual", "richtext", "markdown"]) # From Listmonk
    template_uuid = serializers.UUIDField(required=False, allow_null=True) # API uses UUIDs for FKs
    send_at = serializers.DateTimeField(required=False, allow_null=True)
    status = serializers.ChoiceField(choices=["draft", "scheduled", "running", "paused", "cancelled", "finished"], default="draft")
    campaign_type = serializers.ChoiceField(choices=["regular", "optin"], default="regular")
    tags = serializers.ListField(child=serializers.CharField(max_length=100), required=False, default=list)
    target_list_uuids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)
    # created_by_user_id will be set by the backend from request.user
    archive_settings = CampaignArchiveSettingsSerializer(required=False)
    headers = serializers.ListField(child=CampaignHeaderSerializer(), required=False, default=list)


class CampaignOutputSerializer(CampaignInputSerializer):
    _id = ObjectIdField(read_only=True)
    uuid = serializers.UUIDField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    started_at = serializers.DateTimeField(read_only=True, allow_null=True)
    finished_at = serializers.DateTimeField(read_only=True, allow_null=True)
    stats = CampaignStatSerializer(read_only=True, default=CampaignStatSerializer.Meta.model().default_values) # Provide default for nested
    created_by_user_id = serializers.CharField(read_only=True, allow_null=True) # Or a nested user serializer

    # For read operations, we might want to show names of lists/template instead of just UUIDs/ObjectIds
    # This would be populated by the view using data from the DAL ($lookup or multiple queries)
    template_info = TemplateOutputSerializer(read_only=True, required=False, allow_null=True) # Example
    target_lists_info = MailingListOutputSerializer(many=True, read_only=True, required=False) # Example

    class Meta: # For nested default
        model = CampaignStatSerializer # Dummy for default value of stats

# --- Tracking Event Serializers (if needed for an API, usually just written to DB) ---
# class TrackingEventSerializer(serializers.Serializer):
#     event_type = serializers.ChoiceField(choices=["view", "click"])
#     campaign_uuid = serializers.UUIDField()
#     subscriber_uuid = serializers.UUIDField()
#     timestamp = serializers.DateTimeField(default=serializers.DateTimeField.now) # Handled by DB mostly
#     link_url = serializers.URLField(required=False)
#     link_uuid_ref = serializers.UUIDField(required=False)
#     user_agent = serializers.CharField(required=False)
#     ip_address = serializers.IPAddressField(required=False)

# --- Bounce Serializers (if exposing via API) ---
class BounceOutputSerializer(serializers.Serializer):
    _id = ObjectIdField(read_only=True)
    subscriber_uuid = serializers.UUIDField(source="subscriber_info.uuid", read_only=True) # Example if DAL populates subscriber_info
    subscriber_email = serializers.EmailField(source="subscriber_info.email", read_only=True)
    campaign_uuid = serializers.UUIDField(source="campaign_info.uuid", read_only=True, allow_null=True)
    campaign_name = serializers.CharField(source="campaign_info.name", read_only=True, allow_null=True)
    bounce_type = serializers.ChoiceField(choices=["soft", "hard", "complaint"])
    source_type = serializers.CharField()
    raw_bounce_info = serializers.JSONField()
    reported_at = serializers.DateTimeField()
    created_at = serializers.DateTimeField(read_only=True)


# --- Public Subscription Serializer (as defined before, for clarity) ---
class PublicSubscriptionRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    name = serializers.CharField(required=False, allow_blank=True)
    list_uuids = serializers.ListField(child=serializers.UUIDField(), min_length=1)

# --- Serializers for specific API actions ---
class CampaignStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["draft", "scheduled", "running", "paused", "cancelled", "finished"])

class CampaignTestSendSerializer(serializers.Serializer):
    # Listmonk API takes 'subscribers' (list of emails)
    # but also seems to have other campaign params. For simplicity, just emails.
    emails = serializers.ListField(child=serializers.EmailField(), min_length=1)

class BulkSubscribersActionSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.CharField(), min_length=1) # List of subscriber UUIDs or ObjectIds based on API design

class QueryBasedSubscribersActionSerializer(serializers.Serializer):
    query = serializers.CharField() # This would be a JSON string representing a Mongo query, or a custom DSL
    list_uuids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)

class SubscriberListManagementSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.CharField(), min_length=1) # Subscriber UUIDs or ObjectIds
    action = serializers.ChoiceField(choices=["add", "remove", "unsubscribe"])
    target_list_uuids = serializers.ListField(child=serializers.UUIDField(), min_length=1)
    status = serializers.ChoiceField(choices=["unconfirmed", "confirmed", "unsubscribed"], required=False) # Required for 'add'

    def validate_status(self, value):
        action = self.initial_data.get('action')
        if action == 'add' and not value:
            raise serializers.ValidationError("Status is required when action is 'add'.")
        return value
