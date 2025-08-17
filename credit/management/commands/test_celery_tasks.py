"""
Management command to test Celery tasks for statement workflow
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from credit.tasks.statement_tasks import (
    process_month_end_task,
    process_pending_payments_task,
    calculate_daily_penalties_task,
    add_interest_to_all_users_task,
    daily_statement_maintenance_task
)

User = get_user_model()


class Command(BaseCommand):
    help = 'Test Celery tasks for statement workflow'

    def add_arguments(self, parser):
        parser.add_argument(
            '--task',
            type=str,
            choices=[
                'month_end',
                'pending_payments',
                'daily_penalties',
                'add_interest',
                'daily_maintenance',
                'all'
            ],
            default='all',
            help='Task to test'
        )
        
        parser.add_argument(
            '--user_id',
            type=int,
            help='User ID for specific user tasks'
        )
        
        parser.add_argument(
            '--async',
            action='store_true',
            help='Run tasks asynchronously'
        )

    def handle(self, *args, **options):
        task_name = options['task']
        run_async = options['async']
        
        self.stdout.write(
            self.style.SUCCESS(f"Testing Celery tasks: {task_name}")
        )
        
        if task_name == 'month_end' or task_name == 'all':
            self.test_month_end_task(run_async)
            
        if task_name == 'pending_payments' or task_name == 'all':
            self.test_pending_payments_task(run_async)
            
        if task_name == 'daily_penalties' or task_name == 'all':
            self.test_daily_penalties_task(run_async)
            
        if task_name == 'add_interest' or task_name == 'all':
            self.test_add_interest_task(run_async)
            
        if task_name == 'daily_maintenance' or task_name == 'all':
            self.test_daily_maintenance_task(run_async)

    def test_month_end_task(self, run_async=False):
        self.stdout.write("Testing month-end processing task...")
        
        if run_async:
            task = process_month_end_task.delay()
            self.stdout.write(
                self.style.SUCCESS(f"Month-end task queued: {task.id}")
            )
        else:
            result = process_month_end_task.apply()
            self.stdout.write(
                self.style.SUCCESS(f"Month-end task result: {result.result}")
            )

    def test_pending_payments_task(self, run_async=False):
        self.stdout.write("Testing pending payments task...")
        
        if run_async:
            task = process_pending_payments_task.delay()
            self.stdout.write(
                self.style.SUCCESS(f"Pending payments task queued: {task.id}")
            )
        else:
            result = process_pending_payments_task.apply()
            self.stdout.write(
                self.style.SUCCESS(f"Pending payments task result: {result.result}")
            )

    def test_daily_penalties_task(self, run_async=False):
        self.stdout.write("Testing daily penalties task...")
        
        if run_async:
            task = calculate_daily_penalties_task.delay()
            self.stdout.write(
                self.style.SUCCESS(f"Daily penalties task queued: {task.id}")
            )
        else:
            result = calculate_daily_penalties_task.apply()
            self.stdout.write(
                self.style.SUCCESS(f"Daily penalties task result: {result.result}")
            )

    def test_add_interest_task(self, run_async=False):
        self.stdout.write("Testing add interest task...")
        
        if run_async:
            task = add_interest_to_all_users_task.delay()
            self.stdout.write(
                self.style.SUCCESS(f"Add interest task queued: {task.id}")
            )
        else:
            result = add_interest_to_all_users_task.apply()
            self.stdout.write(
                self.style.SUCCESS(f"Add interest task result: {result.result}")
            )

    def test_daily_maintenance_task(self, run_async=False):
        self.stdout.write("Testing daily maintenance task...")
        
        if run_async:
            task = daily_statement_maintenance_task.delay()
            self.stdout.write(
                self.style.SUCCESS(f"Daily maintenance task queued: {task.id}")
            )
        else:
            result = daily_statement_maintenance_task.apply()
            self.stdout.write(
                self.style.SUCCESS(f"Daily maintenance task result: {result.result}")
            )
