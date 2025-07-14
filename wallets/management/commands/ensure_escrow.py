# wallets/management/commands/ensure_escrow.py
from django.core.management.base import BaseCommand

from wallets.utils.escrow import ensure_escrow_wallet_exists


class Command(BaseCommand):
    help = "Ensure escrow user and wallet exist."

    def handle(self, *args, **kwargs):
        ensure_escrow_wallet_exists()
        self.stdout.write(
            self.style.SUCCESS('Escrow user and wallet ensured!')
            )
