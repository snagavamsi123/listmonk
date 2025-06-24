# listmonk_clone/celery.py
import os
from celery import Celery
from django.conf import settings

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'listmonk_clone.settings')

app = Celery('listmonk_clone')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
# This means Celery will automatically discover tasks in `tasks.py` files
# in your Django apps (e.g., `campaign_manager/tasks.py`).
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')

# Example: To run Celery worker:
# celery -A listmonk_clone worker -l info
#
# To run Celery beat (for scheduled tasks, if any):
# celery -A listmonk_clone beat -l info -S django_celery_beat.schedulers:DatabaseScheduler
# (Requires django-celery-beat package and adding it to INSTALLED_APPS)
# For now, we are focusing on on-demand tasks triggered by application logic.
