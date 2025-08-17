# tickets/management/commands/create_ticket_categories.py
from django.core.management.base import BaseCommand
from tickets.models import TicketCategory


class Command(BaseCommand):
    help = "Create ticket categories from predefined data"

    def handle(self, *args, **options):
        categories_data = [
            {
                "name": "مشکلات فنی",
                "description": "مشکلات مربوط به عملکرد سیستم و اپلیکیشن",
                "icon": "🔧",
                "color": "blue"
            },
            {
                "name": "صورتحساب و پرداخت",
                "description": "سوالات مربوط به صورتحساب و روش‌های پرداخت",
                "icon": "💳",
                "color": "green"
            },
            {
                "name": "حساب کاربری",
                "description": "مشکلات مربوط به ثبت‌نام، ورود و تنظیمات حساب",
                "icon": "👤",
                "color": "purple"
            },
            {
                "name": "تراکنش‌های مالی",
                "description": "مشکلات مربوط به انتقال وجه و تراکنش‌ها",
                "icon": "💰",
                "color": "yellow"
            },
            {
                "name": "کیف پول",
                "description": "سوالات مربوط به کیف پول و موجودی",
                "icon": "💼",
                "color": "orange"
            },
            {
                "name": "فروشگاه",
                "description": "مشکلات مربوط به فروشگاه و درگاه پرداخت",
                "icon": "🏪",
                "color": "red"
            },
            {
                "name": "سوالات عمومی",
                "description": "سوالات عمومی و سایر موارد",
                "icon": "❓",
                "color": "gray"
            }
        ]

        created_count = 0
        for category_data in categories_data:
            category, created = TicketCategory.objects.get_or_create(
                name=category_data["name"],
                defaults={
                    "description": category_data["description"],
                    "icon": category_data["icon"],
                    "color": category_data["color"],
                }
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created category: {category.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Category already exists: {category.name}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {created_count} ticket categories')
        )
