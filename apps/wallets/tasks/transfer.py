# wallets/tasks/transfer.py

from celery import shared_task

from wallets.services import expire_pending_transfer_requests


@shared_task
def task_expire_pending_transfer_requests():
    expire_pending_transfer_requests()
