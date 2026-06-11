# apps/accounting/management/commands/seed_payroll_foundation.py

from django.core.management.base import BaseCommand

from apps.accounting.seeds.payroll_config import seed_payroll_foundation_2026


class Command(BaseCommand):
    help = "Create or update initial payroll foundation records for TownLIT."

    def handle(self, *args, **options):
        seed_payroll_foundation_2026()

        self.stdout.write(
            self.style.SUCCESS("Payroll foundation seeded successfully.")
        )
        
# docker compose exec backend python manage.py seed_payroll_foundation