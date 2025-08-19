# saeedpay/celery.py

import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'saeedpay.settings')

app = Celery('saeedpay')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()

app.conf.update(
    task_track_started=True,
    task_time_limit=30 * 60,  # 30m hard
    task_soft_time_limit=25 * 60,  # 25m soft
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)
