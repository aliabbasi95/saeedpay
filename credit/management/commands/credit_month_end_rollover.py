# credit/management/commands/credit_month_end_rollover.py

from django.core.management.base import BaseCommand

from credit.services.use_cases import StatementUseCases


class Command(BaseCommand):
    help = (
        "Close all CURRENT statements that belong to past Persian months, "
        "create the new CURRENT per user with carry-over, and add monthly interest on negative carry-overs."
    )

    def handle(self, *args, **options):
        result = StatementUseCases.perform_month_end_rollover()
        self.stdout.write(
            self.style.SUCCESS(
                f"Closed: {result['statements_closed']}, "
                f"Created: {result['statements_created']}, "
                f"Interest lines: {result['interest_lines_added']}"
            )
        )
