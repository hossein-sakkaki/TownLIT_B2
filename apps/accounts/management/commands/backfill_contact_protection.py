# apps/accounts/management/commands/backfill_contact_protection.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = "Legacy contact backfill is unavailable after phone column removal."
    def handle(self, *args, **options):
        raise CommandError("Stage A backfill has finished; use verify_contact_protection.")
