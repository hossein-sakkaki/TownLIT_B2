# apps/accounts/management/commands/backfill_address_additional_encrypted.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Retired after the encrypted-only Address cutover."

    def handle(self, *args, **options):
        raise CommandError(
            "Legacy plaintext is no longer present; use verify_address_additional_encrypted."
        )
