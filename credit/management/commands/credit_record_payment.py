# credit/management/commands/credit_record_payment.py

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from credit.services.use_cases import StatementUseCases
from wallets.models import Transaction as WalletTransaction

User = get_user_model()


class Command(BaseCommand):
    help = "Record a PAYMENT line on the user's CURRENT statement (payments never touch the pending snapshot)."

    def add_arguments(self, parser):
        parser.add_argument("user_id", type=int, help="User ID")
        parser.add_argument(
            "amount", type=int, help="Payment amount (Rials, positive)"
        )
        parser.add_argument(
            "--transaction-id",
            type=int,
            default=None,
            help="Optional wallets.Transaction ID to link",
        )
        parser.add_argument(
            "--description",
            type=str,
            default="Payment",
            help="Optional payment description",
        )

    def handle(self, *args, **options):
        user_id = options["user_id"]
        amount = options["amount"]
        transaction_id = options["transaction_id"]
        description = options["description"]

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise CommandError(f"User {user_id} not found")

        transaction_obj = None
        if transaction_id is not None:
            try:
                transaction_obj = WalletTransaction.objects.get(
                    pk=transaction_id
                )
            except WalletTransaction.DoesNotExist:
                raise CommandError(f"Transaction {transaction_id} not found")

        try:
            stmt = StatementUseCases.record_payment_on_current_statement(
                user=user,
                amount=amount,
                payment_transaction=transaction_obj,
                description=description,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Payment recorded on CURRENT statement #{stmt.id} for user {user_id}"
                )
            )
        except Exception as e:
            raise CommandError(str(e))
