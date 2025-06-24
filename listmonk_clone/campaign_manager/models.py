# This app (campaign_manager) uses MongoDB via Pymongo for its primary data storage
# (subscribers, campaigns, lists, templates, etc.) as defined in the
# db_access package and mongodb_schema_design.md.

# Django ORM models are not used for these entities.
# This file is kept to ensure Django recognizes 'campaign_manager' as an app
# and for potential future use with Django's utility features if needed,
# or if other Django apps need to define ORM models that might conceptually
# link to campaign_manager entities via non-database relations or utilities.

# from django.db import models
# Create your models here.
