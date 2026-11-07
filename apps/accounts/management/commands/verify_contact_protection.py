# apps/accounts/management/commands/verify_contact_protection.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#
"""Verify ciphertext, indexes and row binding without disclosing PII."""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from apps.core.crypto.blind_index import BlindIndexer
from apps.core.crypto.field_protection import FieldProtector
from apps.accounts.services.contact_protection import (
    decrypt_contact, index_matches,
)

class Command(BaseCommand):
    help = "Validate encrypted phone-only and email shadow persistence."

    def handle(self, *args, **options):
        FieldProtector.from_environment()
        BlindIndexer.from_environment()
        User = get_user_model()
        rows = encrypted_fields = errors = 0
        for user in User._base_manager.order_by("pk").iterator(chunk_size=250):
            rows += 1
            for name, storage, index_storage in (
                ("email", "email_encrypted", "email_blind_index"),
                ("mobile_number", "mobile_number_encrypted", "mobile_number_blind_index"),
            ):
                try:
                    # Reading the logical phone property also decrypts; catch
                    # its integrity errors rather than aborting the entire scan.
                    value = getattr(user, name)
                    encrypted = getattr(user, storage)
                    indexed = getattr(user, index_storage)
                    if encrypted is None:
                        if value is not None or indexed is not None:
                            errors += 1
                        continue
                    recovered = decrypt_contact(user, encrypted, field=name)
                    if recovered != value or not index_matches(indexed, value, field=name):
                        errors += 1
                    else:
                        encrypted_fields += 1
                except Exception:
                    errors += 1
        self.stdout.write(f"rows={rows} encrypted_fields={encrypted_fields} errors={errors}")
        if errors:
            raise CommandError("Contact verification failed.")
