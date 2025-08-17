# saeedpay/celery.py
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'saeedpay.settings')

# Create Celery app - broker URL will be configured from Django settings
app = Celery('saeedpay')

# Load configuration from Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all Django apps
app.autodiscover_tasks()
