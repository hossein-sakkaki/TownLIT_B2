# apps/accounting/management/commands/seed_accounting_periods.py

from django.core.management.base import BaseCommand

from apps.accounting.services.period_generation_service import (
    generate_fiscal_year_periods,
)


class Command(BaseCommand):
    help = "Create or update monthly accounting periods for a TownLIT fiscal year."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fy-start-year",
            type=int,
            required=True,
            help="Calendar year in which the fiscal year starts. Example: 2025 for FY2026.",
        )

    def handle(self, *args, **options):
        fy_start_year = options["fy_start_year"]

        result = generate_fiscal_year_periods(
            fy_start_year=fy_start_year,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"{result.created_or_updated_count} accounting periods created/updated for {result.fiscal_year_label}."
            )
        )

# python manage.py seed_accounting_periods --fy-start-year 2025
# /accounting/periods/generate/