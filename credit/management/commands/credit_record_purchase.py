# credit/management/commands/credit_record_purchase.py

from django.core.management.base import BaseCommand, CommandError

from credit.services.use_cases import StatementUseCases


class Command(BaseCommand):
    help = "Record a PURCHASE line from a SUCCESS wallets.Transaction id on the buyer's CURRENT statement."

    def add_arguments(self, parser):
        parser.add_argument(
            "transaction_id", type=int,
            help="Wallets Transaction ID (must be SUCCESS)"
        )

    def handle(self, *args, **options):
        transaction_id = options["transaction_id"]
        try:
            stmt = StatementUseCases.record_successful_purchase_from_transaction(
                transaction_id, description="Purchase"
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Purchase recorded on CURRENT statement #{stmt.id} for user {stmt.user_id}"
                )
            )
        except Exception as e:
            raise CommandError(str(e))
