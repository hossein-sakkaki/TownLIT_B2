# apps/accounting/management/commands/seed_bank_institutions.py

from django.core.management.base import BaseCommand

from apps.accounting.seeds.bank_institutions import seed_bank_institutions


class Command(BaseCommand):
    help = "Create or update default bank institutions"

    def handle(self, *args, **options):
        seed_bank_institutions()
        self.stdout.write(
            self.style.SUCCESS("Bank institutions seeded successfully.")
        )

# docker compose exec backend python manage.py seed_bank_institutions