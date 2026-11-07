# apps/accounts/management/commands/verify_identity_private_fields.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Encrypted-only IdentityVerification integrity check, without displaying secrets."""

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models.identity import IdentityVerification
from apps.accounts.services.identity_private_fields import decrypt_identity_field


class Command(BaseCommand):
    help = "Verify identity private fields using their authenticated row binding."

    def handle(self, *args, **options):
        checked = errors = 0
        for row in IdentityVerification.objects.only(
            "id", "user_id", "provider_payload_encrypted", "notes_encrypted"
        ).iterator(chunk_size=200):
            checked += 1
            try:
                for name in ("provider_payload", "notes"):
                    decrypt_identity_field(name, getattr(row, f"{name}_encrypted"), row.user_id)
            except Exception:
                errors += 1
                self.stderr.write(f"IdentityVerification id={row.pk}: integrity validation failed (no sensitive values)")
        self.stdout.write(f"identity_rows={checked} errors={errors}")
        if errors:
            raise CommandError("Encrypted identity integrity verification failed.")
