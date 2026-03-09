# apps/accounting/management/commands/seed_chart_of_accounts.py

from django.core.management.base import BaseCommand
from apps.accounting.seeds.chart_of_accounts import seed_chart_of_accounts


class Command(BaseCommand):
    help = "Create or update the default Chart of Accounts"

    def handle(self, *args, **options):
        seed_chart_of_accounts()
        self.stdout.write(
            self.style.SUCCESS("Chart of Accounts seeded successfully.")
        )


# docker compose exec backend python manage.py seed_chart_of_accounts
