# apps/credit/management/commands/credit_finalize_due_windows.py

from django.core.management.base import BaseCommand

from apps.credit.services.use_cases import StatementUseCases


class Command(BaseCommand):
    help = (
        "Finalize PENDING_PAYMENT statements whose due_date has passed by reading payments made on CURRENT "
        "within the due window and applying penalty to CURRENT if minimum payment was not met."
    )

    def handle(self, *args, **options):
        result = StatementUseCases.finalize_due_windows()
        self.stdout.write(
            self.style.SUCCESS(
                f"Finalized: {result.finalized_count}, "
                f"Closed without penalty: {result.closed_without_penalty_count}, "
                f"Closed with penalty: {result.closed_with_penalty_count}"
            )
        )
