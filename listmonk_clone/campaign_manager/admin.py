# The campaign_manager app uses MongoDB directly via Pymongo,
# so its main entities (subscribers, campaigns, etc.) are not Django ORM models
# and cannot be registered with the standard Django admin site in the usual way.

# To manage MongoDB data via a Django admin-like interface, you would typically
# need to use a third-party package like 'django-mongodb-admin' or build
# custom admin views that interact with your Pymongo DAL.

# from django.contrib import admin
# Register your models here.
