# apps/accounts/management/commands/backfill_user_privacy_wave.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Migration command intentionally unavailable after the encrypted-only cutover."""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Stage-A-only command; no longer applicable after plaintext column removal."

    def handle(self, *args, **options):
        raise CommandError(
            "This command is Stage-A-only. Use verify_user_privacy_wave after cutover."
        )
