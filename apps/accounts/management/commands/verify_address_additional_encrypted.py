# apps/accounts/management/commands/verify_address_additional_encrypted.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Development-only ciphertext integrity check. Does not expose plaintext."""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import Address
from apps.core.crypto.field_protection import FieldProtectionError, FieldProtector


class Command(BaseCommand):
    help = "Verify encrypted Address delivery instructions without logging values."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("This verification command is Development-only.")
        try:
            protector = FieldProtector.from_environment()
        except FieldProtectionError as exc:
            raise CommandError(str(exc)) from exc
        count = protected = 0
        for row in (Address.objects.only("id", "additional_encrypted")
                    .order_by("id").iterator(chunk_size=200)):
            count += 1
            if row.additional_encrypted is None:
                continue
            try:
                protector.reveal(row.additional_encrypted,
                                 field="accounts.Address.additional", row_id=row.pk)
            except FieldProtectionError as exc:
                raise CommandError(f"Encrypted Address row {row.pk} failed verification.") from exc
            protected += 1
        self.stdout.write(f"Verified Address rows: total={count}, encrypted={protected}, errors=0")
