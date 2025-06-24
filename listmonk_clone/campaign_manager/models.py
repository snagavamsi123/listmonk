import uuid
from django.db import models
# from django.contrib.postgres.fields import ArrayField # Alternative for tags if only targeting PostgreSQL
from django.conf import settings # To link to Django's User model if needed later

# ENUM Choices based on schema.sql

class ListType(models.TextChoices):
    PUBLIC = 'public', 'Public'
    PRIVATE = 'private', 'Private'
    TEMPORARY = 'temporary', 'Temporary' # Though 'temporary' might not be needed long-term

class ListOptin(models.TextChoices):
    SINGLE = 'single', 'Single Opt-in'
    DOUBLE = 'double', 'Double Opt-in'

class SubscriberStatus(models.TextChoices):
    ENABLED = 'enabled', 'Enabled'
    DISABLED = 'disabled', 'Disabled'
    BLOCKLISTED = 'blocklisted', 'Blocklisted'

class SubscriptionStatus(models.TextChoices):
    UNCONFIRMED = 'unconfirmed', 'Unconfirmed'
    CONFIRMED = 'confirmed', 'Confirmed'
    UNSUBSCRIBED = 'unsubscribed', 'Unsubscribed'

class CampaignStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    RUNNING = 'running', 'Running'
    SCHEDULED = 'scheduled', 'Scheduled'
    PAUSED = 'paused', 'Paused'
    CANCELLED = 'cancelled', 'Cancelled'
    FINISHED = 'finished', 'Finished'

class CampaignType(models.TextChoices):
    REGULAR = 'regular', 'Regular'
    OPTIN = 'optin', 'Opt-in' # For opt-in confirmation campaigns

class ContentType(models.TextChoices):
    RICHTEXT = 'richtext', 'Rich Text'
    HTML = 'html', 'HTML'
    PLAIN = 'plain', 'Plain Text'
    MARKDOWN = 'markdown', 'Markdown'
    VISUAL = 'visual', 'Visual Builder' # Visual builder might be a stretch goal

class BounceType(models.TextChoices):
    SOFT = 'soft', 'Soft'
    HARD = 'hard', 'Hard'
    COMPLAINT = 'complaint', 'Complaint'

class TemplateType(models.TextChoices):
    CAMPAIGN = 'campaign', 'Campaign'
    CAMPAIGN_VISUAL = 'campaign_visual', 'Campaign Visual'
    TRANSACTIONAL = 'tx', 'Transactional'


# Models

class Subscriber(models.Model):
    id = models.BigAutoField(primary_key=True) # Matches SERIAL PRIMARY KEY
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    email = models.EmailField(unique=True, db_index=True) # Lowercase index handled by DB or app logic
    name = models.TextField() # In Listmonk schema it's TEXT NOT NULL
    attribs = models.JSONField(default=dict)
    status = models.CharField(
        max_length=20,
        choices=SubscriberStatus.choices,
        default=SubscriberStatus.ENABLED
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.email

    class Meta:
        ordering = ['-created_at']


class MailingList(models.Model): # Renamed from 'List' to avoid conflict with Python's list
    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.TextField()
    list_type = models.CharField( # Renamed from 'type'
        max_length=20,
        choices=ListType.choices,
        db_column='type' # To match Listmonk's schema for easier data migration
    )
    optin = models.CharField(
        max_length=20,
        choices=ListOptin.choices,
        default=ListOptin.SINGLE
    )
    tags = models.JSONField(default=list, blank=True) # Using JSONField for array of strings
    description = models.TextField(default='', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    subscribers = models.ManyToManyField(
        Subscriber,
        through='Subscription',
        related_name='mailing_lists'
    )

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        # db_table = 'lists' # To match Listmonk's schema name exactly for migration


class Subscription(models.Model): # Represents subscriber_lists table
    # id = models.BigAutoField(primary_key=True) # Implicitly added by Django
    subscriber = models.ForeignKey(Subscriber, on_delete=models.CASCADE)
    mailing_list = models.ForeignKey(MailingList, on_delete=models.CASCADE, db_column='list_id')
    meta = models.JSONField(default=dict, blank=True) # Not sure what this is for yet
    status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.UNCONFIRMED
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('subscriber', 'mailing_list')
        ordering = ['-created_at']
        # db_table = 'subscriber_lists' # To match Listmonk's schema name


class EmailTemplate(models.Model): # Renamed from Template
    id = models.BigAutoField(primary_key=True)
    name = models.TextField()
    template_type = models.CharField( # Renamed from 'type'
        max_length=20,
        choices=TemplateType.choices,
        default=TemplateType.CAMPAIGN,
        db_column='type'
    )
    subject = models.TextField(blank=True) # Subject is NOT NULL in schema, but can be blank for non-tx
    body = models.TextField()
    body_source = models.TextField(null=True, blank=True) # For visual builder JSON
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        # unique_together = (('is_default', 'template_type'),) # Listmonk has: CREATE UNIQUE INDEX ON templates (is_default) WHERE is_default = true;
        # This is harder to enforce directly in Django models for partial unique index. Can be done at DB level or with clean() method.
        # For now, ensure only one is_default=True per type via application logic or admin.
        # db_table = 'templates'


class Campaign(models.Model):
    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.TextField()
    subject = models.TextField()
    from_email = models.TextField() # Could be CharField or EmailField if validated
    body = models.TextField()
    body_source = models.TextField(null=True, blank=True) # For visual builder
    alt_body = models.TextField(null=True, blank=True, db_column='altbody') # Matches 'altbody'
    content_type = models.CharField(
        max_length=20,
        choices=ContentType.choices,
        default=ContentType.RICHTEXT
    )
    send_at = models.DateTimeField(null=True, blank=True)
    headers = models.JSONField(default=list, blank=True) # Array of key-value pairs
    status = models.CharField(
        max_length=20,
        choices=CampaignStatus.choices,
        default=CampaignStatus.DRAFT
    )
    tags = models.JSONField(default=list, blank=True)
    campaign_type = models.CharField( # Renamed from 'type'
        max_length=20,
        choices=CampaignType.choices,
        default=CampaignType.REGULAR,
        db_column='type'
    )
    messenger = models.TextField(default='email') # 'email' or custom from settings
    template = models.ForeignKey(EmailTemplate, on_delete=models.SET_NULL, null=True, blank=True)

    # Progress and stats
    to_send = models.IntegerField(default=0)
    sent = models.IntegerField(default=0)
    # max_subscriber_id and last_subscriber_id are for Listmonk's internal sending queue, might not be needed directly
    # or implemented differently with Celery.

    # Publishing / Archive
    archive = models.BooleanField(default=False)
    archive_slug = models.SlugField(null=True, blank=True, unique=True) # TEXT NULL UNIQUE -> SlugField
    archive_template = models.ForeignKey(
        EmailTemplate,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='archived_campaigns'
    )
    archive_meta = models.JSONField(default=dict, blank=True)

    started_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # M2M for lists this campaign is sent to
    target_lists = models.ManyToManyField(
        MailingList,
        through='CampaignListMembership',
        related_name='campaigns'
    )

    # Integration: Link to the user who created the campaign
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, # Or models.PROTECT, or models.CASCADE depending on policy
        null=True,
        blank=True,
        related_name='created_campaigns'
    )

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-created_at']
        # db_table = 'campaigns'


class CampaignListMembership(models.Model): # campaign_lists table
    # id = models.BigAutoField(primary_key=True) # Implicit
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE)
    mailing_list = models.ForeignKey(MailingList, on_delete=models.SET_NULL, null=True, db_column='list_id') # SET_NULL as per schema
    # Store list_name in case list is deleted, as per schema comment
    list_name_snapshot = models.TextField(db_column='list_name')

    class Meta:
        unique_together = ('campaign', 'mailing_list') # If list_id can be NULL, this might need adjustment or be handled at DB level if list_id is part of the key
        # db_table = 'campaign_lists'

    def save(self, *args, **kwargs):
        if self.mailing_list and not self.list_name_snapshot:
            self.list_name_snapshot = self.mailing_list.name
        super().save(*args, **kwargs)


class CampaignView(models.Model):
    id = models.BigAutoField(primary_key=True)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE)
    subscriber = models.ForeignKey(Subscriber, on_delete=models.SET_NULL, null=True, blank=True) # SET_NULL as per schema
    created_at = models.DateTimeField(auto_now_add=True, db_index=True) # Index on date part handled by DB or ORM query

    class Meta:
        ordering = ['-created_at']
        # db_table = 'campaign_views'


class MediaAsset(models.Model): # media table
    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    provider = models.TextField(default='') # eg: filesystem, s3
    # Consider FileField for filename if managing uploads via Django
    filename = models.TextField() # For now, text to store path/name
    file = models.FileField(upload_to='media_assets/', blank=True, null=True) # Django's way
    content_type = models.CharField(max_length=100, default='application/octet-stream')
    thumb = models.TextField(blank=True) # Path to thumbnail or data URI
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.filename

    class Meta:
        # db_table = 'media'
        indexes = [
            models.Index(fields=['provider', 'filename']),
        ]


class CampaignMediaAsset(models.Model): # campaign_media table
    # id = models.BigAutoField(primary_key=True) # Implicit
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE)
    media_asset = models.ForeignKey(MediaAsset, on_delete=models.SET_NULL, null=True, db_column='media_id')
    # Store filename in case media is deleted
    filename_snapshot = models.TextField(db_column='filename')

    class Meta:
        unique_together = ('campaign', 'media_asset') # If media_id can be NULL, this might need adjustment
        # db_table = 'campaign_media'

    def save(self, *args, **kwargs):
        if self.media_asset and not self.filename_snapshot:
            self.filename_snapshot = self.media_asset.filename
        super().save(*args, **kwargs)


class Link(models.Model):
    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    url = models.URLField(max_length=2048, unique=True) # TEXT UNIQUE -> URLField
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.url

    class Meta:
        ordering = ['-created_at']
        # db_table = 'links'


class LinkClick(models.Model):
    id = models.BigAutoField(primary_key=True)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, null=True, blank=True) # Can be null if click is not campaign related
    link = models.ForeignKey(Link, on_delete=models.CASCADE)
    subscriber = models.ForeignKey(Subscriber, on_delete=models.SET_NULL, null=True, blank=True) # SET_NULL as per schema
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        # db_table = 'link_clicks'


class Bounce(models.Model):
    id = models.BigAutoField(primary_key=True)
    subscriber = models.ForeignKey(Subscriber, on_delete=models.CASCADE)
    campaign = models.ForeignKey(Campaign, on_delete=models.SET_NULL, null=True, blank=True) # SET_NULL as per schema
    bounce_type = models.CharField( # Renamed from 'type'
        max_length=20,
        choices=BounceType.choices,
        default=BounceType.HARD,
        db_column='type'
    )
    source = models.TextField(default='', blank=True) # eg: SES, Sendgrid, IMAP
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        # db_table = 'bounces'

# Skipping 'settings', 'roles', 'users', 'sessions' tables from Listmonk as they
# will be handled by Django's built-in systems or project-specific settings.
# Materialized views will be replicated by ORM queries or custom SQL when needed for reporting.

# Note on db_column and db_table:
# Using db_column for fields like 'type' when the Django field name is different
# (e.g., 'list_type') can help if you plan a direct data migration strategy from
# an existing Listmonk database, as it keeps the column names the same.
# Similarly, Meta.db_table could be used if you want Django to use the exact same
# table names as Listmonk. For a fresh setup, these are not strictly necessary
# and Django's default naming conventions (appname_modelname for tables, fieldname for columns)
# would work fine. I've added them as comments for consideration during migration.
# For now, I will keep them commented out to use Django defaults unless a specific mapping is critical.
# I've kept db_column for the 'type' fields as those are common keywords.

# The `VARCHAR(100)[]` for tags is implemented as JSONField.
# If this application strictly uses PostgreSQL, `django.contrib.postgres.fields.ArrayField(models.CharField(max_length=100))`
# would be a more direct translation for `tags` fields. I've used JSONField for broader DB compatibility for now.

# The unique index `CREATE UNIQUE INDEX ON templates (is_default) WHERE is_default = true;`
# is a partial unique index. This is not directly supported by Django ORM's `unique_together` or `UniqueConstraint`
# in a cross-database way. This constraint would typically be enforced at the database level directly
# or through application logic (e.g., in a model's `clean()` or `save()` method, or form validation)
# to ensure only one template of a given type can be `is_default=True`.
# For now, I've commented this out and it will be an application logic concern.
# Example of how it could be handled in save():
# def save(self, *args, **kwargs):
#     if self.is_default:
#         EmailTemplate.objects.filter(template_type=self.template_type, is_default=True).exclude(pk=self.pk).update(is_default=False)
#     super().save(*args, **kwargs)
# This logic should be carefully tested.

# `max_subscriber_id` and `last_subscriber_id` in Campaign model were related to Listmonk's batch sending.
# This will likely be handled differently with Celery tasks, so I've omitted them for now.
# They can be added if a similar batching cursor mechanism is chosen for Django.
