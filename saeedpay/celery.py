# saeedpay/celery.py
import os
from celery import Celery
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'saeedpay.settings')
REDIS_PASSWORD = getattr(settings, 'REDIS_PASSWORD', None)

app = Celery('saeedpay', broker=f'redis://:{REDIS_PASSWORD}@localhost:6379')

app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
