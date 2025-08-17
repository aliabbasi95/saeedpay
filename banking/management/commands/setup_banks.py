from django.core.management.base import BaseCommand
from banking.models import Bank


class Command(BaseCommand):
    help = 'Create initial banks for the banking system'

    def handle(self, *args, **options):
        banks_data = [
            {"name": "بانک ملت", "color": "#E53E3E"},
            {"name": "بانک ملی ایران", "color": "#1976D2"},
            {"name": "بانک صنعت و معدن", "color": "#718096"},
            {"name": "بانک رفاه کارگران", "color": "#38A169"},
            {"name": "بانک مسکن", "color": "#D69E2E"},
            {"name": "بانک سپه", "color": "#805AD5"},
            {"name": "بانک کشاورزی", "color": "#48BB78"},
            {"name": "بانک صادرات ایران", "color": "#3182CE"},
            {"name": "بانک توسعه صادرات", "color": "#2D3748"},
            {"name": "بانک توسعه تعاون", "color": "#4A5568"},
            {"name": "پست بانک ایران", "color": "#2B6CB0"},
            {"name": "بانک اقتصاد نوین", "color": "#319795"},
            {"name": "بانک پارسیان", "color": "#DD6B20"},
            {"name": "بانک پاسارگاد", "color": "#0BC5EA"},
            {"name": "بانک کارآفرین", "color": "#9F7AEA"},
            {"name": "بانک سامان", "color": "#2F855A"},
            {"name": "بانک سینا", "color": "#B794F6"},
            {"name": "بانک شهر", "color": "#F56565"},
            {"name": "بانک دی", "color": "#4299E1"},
            {"name": "بانک آینده", "color": "#68D391"},
        ]

        created_count = 0
        for bank_data in banks_data:
            bank, created = Bank.objects.get_or_create(
                name=bank_data["name"],
                defaults={"color": bank_data["color"]}
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created bank: {bank.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Bank already exists: {bank.name}')
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'Setup complete. Created {created_count} new banks. '
                f'Total banks: {Bank.objects.count()}'
            )
        )