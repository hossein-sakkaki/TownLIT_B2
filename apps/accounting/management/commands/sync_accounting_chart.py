# apps/accounting/management/commands/sync_accounting_chart.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from django.core.management.base import BaseCommand

from apps.accounting.seeds.chart_of_accounts import seed_chart_of_accounts


class Command(BaseCommand):
    help = "Idempotently sync the TownLIT accounting chart of accounts."

    def handle(self, *args, **options):
        seed_chart_of_accounts()
        self.stdout.write(self.style.SUCCESS("TownLIT accounting chart synchronized."))
