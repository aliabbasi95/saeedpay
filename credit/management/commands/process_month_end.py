#!/usr/bin/env python
"""
Management command to handle complete month-end processing
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from persiantools.jdatetime import JalaliDate
from credit.models import Statement


class Command(BaseCommand):
    help = "Process month-end: close old statements, create new ones, add interest"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Run without making changes",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        self.stdout.write("Starting month-end processing...")

        if dry_run:
            self.stdout.write(self.style.WARNING("Running in DRY RUN mode"))

        # Step 1: Close monthly statements
        self.stdout.write("Step 1: Closing monthly statements...")
        if not dry_run:
            Statement.objects.close_monthly_statements()
            self.stdout.write(self.style.SUCCESS("Monthly statements closed"))
        else:
            # Show what would happen
            from persiantools.jdatetime import JalaliDate

            today = JalaliDate.today()
            current_statements = Statement.objects.filter(status="current")

            to_close = []
            for statement in current_statements:
                if statement.year < today.year or (
                    statement.year == today.year and statement.month < today.month
                ):
                    to_close.append(statement)

            self.stdout.write(
                f"DRY RUN: Would close {len(to_close)} statements and create new ones"
            )
            for stmt in to_close:
                self.stdout.write(
                    f"  - User {stmt.user.id}: {stmt.year}/{stmt.month} -> {today.year}/{today.month}"
                )

        self.stdout.write("Month-end processing completed!")
