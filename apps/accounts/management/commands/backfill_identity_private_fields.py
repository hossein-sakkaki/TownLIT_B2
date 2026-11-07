# apps/accounts/management/commands/backfill_identity_private_fields.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Disabled after encrypted-only migration; no legacy fields remain."

    def handle(self, *args, **options):
        raise CommandError("Legacy identity backfill retired. Use verify_identity_private_fields.")
